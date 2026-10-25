# CareerLens — MVP Plan (v0.1, pending approval)

> Status: **planning only, no code written yet.** This file is the source of truth for scope and the
> project checklist. Update it at the end of every milestone.

## 0. Decisions

| # | Decision | Status |
|---|---|---|
| D1 | Email/password login from Day 1; every query scoped to the current user | **Decided** |
| D2 | Postgres (and later the whole app) runs in Docker; user installs Docker Desktop + WSL 2 | **Decided** |
| D3 | Deploy all three parts together (one Docker Compose stack on a VPS, or one Railway/Render project) — host chosen on Day 4 | **Decided (host TBD)** |
| D4 | AI provider: **Google Gemini** via the official `google-genai` Python SDK, behind the `AIProvider` interface. Core still works with no AI. Structured output (JSON schema from Pydantic) + our own validation. Key in `backend/.env` as `GEMINI_API_KEY`, never in the frontend. Consent screen states CVs are sent to Google; develop with self-written test CVs on the free tier, and don't send real CVs unless billing is enabled or the current terms say free-tier data isn't used for training. | **Decided** |

---

## 1. Product specification

**One sentence:** CareerLens turns each job application into evidence — what the job asks for, what
your CV actually shows, what you prepared, what happened in the recruitment rounds — and feeds that
evidence back into what you should learn and fix next.

### 1.1 The loop, as data

```
JobApplication ──(job description)──► RequirementAnalysis ──► JobRequirement[]
       │                                    ▲                         │
       │ uses                                │ analysed against        │ each has
       ▼                                    │                         ▼
   CVVersion ──► CVSection ──► CVPassage ───┘◄──── RequirementEvidence (links requirement ↔ passage)
                                    │                         │
                                    │                         ├──► CVRecommendation (presentation / evidence gap /
                                    │                         │      potential capability gap / unverified claim)
                                    │                         ▼
                                    │                     SkillGap ◄──────────────┐
                                    │                         │  motivates        │ new evidence
                                    │                         ▼                   │ (GapEvidence)
       RecruitmentRound ◄──── Task (learning | preparation) ──► TaskAttempt       │
             │                                                                    │
             ├──► Journal ──► Question ──► QuestionAttempt ───────────────────────┘
             │                    │
             └── RecruitmentEvent (append-only history of dates, statuses, results)

             GapReassessment: "was this gap improved?" — each one cites the attempts/questions behind it.
             Insights: computed on read from all of the above, each with source records + observation count.
```

Concretely, the connections the code must enforce:

| From | To | How |
|---|---|---|
| Requirement not evidenced in CV | CV recommendation | Every `not_found_in_cv` / `partial` requirement gets a recommendation of the right kind |
| Requirement | Skill gap | Only when the user confirms they lack it, *or* a later assessment shows difficulty. "Not found in CV" alone creates an **evidence gap**, never a capability gap |
| Skill gap | Learning task | `task.skill_gap_id` |
| Requirement / gap | Preparation task for a round | `task.recruitment_round_id` + `task.job_requirement_id` |
| Round | Journal | `journal.recruitment_round_id` |
| Journal | Questions | Questions are extracted into the question bank, `question.journal_id` |
| Question the user struggled with | Skill gap | `gap_evidence.question_id` (new or existing gap) |
| Task attempts / question re-attempts | Gap reassessment | `gap_reassessment` cites the attempts it is based on |
| Gaps across applications | Next application's priorities | A gap is per-user, linked to many requirements across applications |

### 1.2 Truthfulness model (applies everywhere)

Every generated or inferred record carries an **origin**: `user` · `rule_engine` · `ai`.
Every claim about the candidate carries a **basis**:

| Basis | Meaning | Example |
|---|---|---|
| `cv_text` | Literally present in the CV | "FastAPI" appears in a project bullet |
| `user_confirmed` | User asserted it | "I used Docker at my internship, it's just not on the CV" |
| `recorded_outcome` | From a journal / attempt record | "Could not answer SQL window functions question" |
| `interviewer_feedback` | Explicitly stated by an interviewer | Kept separate from user interpretation |
| `user_interpretation` | User's own reading of events | "I think they wanted more depth" |
| `hypothesis` | Inference by rules or AI, unconfirmed | "May need more practice with system design" |

UI shows the basis as a badge. Nothing with basis `hypothesis` is ever displayed as a fact.

### 1.3 Evidence classification

| Value | Rule (non-AI engine) |
|---|---|
| `demonstrated` | Requirement term found in an experience/project/internship passage that describes usage |
| `partially_demonstrated` | Term only in a skills list, or related-but-not-equal term in a project (e.g. "MySQL" for "PostgreSQL") |
| `not_found_in_cv` | No match in the analysed document. **UI text: "Not found in this CV — this does not mean you lack the skill."** |
| `needs_verification` | Vague/soft requirement ("strong communication"), or CV parse quality was poor |

Separately, the user can record a **self-report** per requirement: `unknown` (default) ·
`have_not_on_cv` · `do_not_have` · `learning`. This is what distinguishes "missing CV evidence" from
"verified lack of skill" — and it's tested.

### 1.4 Coverage score (if shown)

`CV evidence coverage = demonstrated_required / total_required`, shown alongside partial and
needs-verification counts. Excludes preferred and `importance=uncertain` requirements. Labelled:
*"How much of this job's required list your CV visibly evidences. Not a prediction of hiring outcome."*

### 1.5 Explicitly out of scope for the MVP
Email/push notifications, OCR for scanned PDFs, multi-file CV editing/export, calendar sync, team
features, automatic job-board scraping, any "hire probability".

---

## 2. Database schema

Conventions: PostgreSQL, UUID primary keys, `created_at`/`updated_at` timestamptz on every table.
Enums are stored as `VARCHAR + CHECK` (SQLAlchemy `Enum(native_enum=False)`) — far easier to evolve
with Alembic than native Postgres enums. Every top-level table has `user_id`; child tables are reached
through their parent and service queries always join back to the owner.

**Revisions vs. your suggested entity list:**
- `LearningTask` + `PreparationTask` → one **`tasks`** table with `kind` (they share status, priority,
  due date, attempts; keeping two tables duplicates everything).
- `RequirementEvidence` is a **link table** (requirement ↔ CV passage); the classification lives on the
  requirement itself, because one requirement has one verdict but many passages.
- Added **`requirement_analyses`** so an application can be re-analysed against a new CV version
  without losing the old analysis, and so returning to a job never repeats completed work.
- Added **`cv_passages`** so evidence points at exact text (char offsets), not just a section.
- **`Insight` is not stored** — computed on read from real records. No stale/invented insights.
- `RecruitmentEvent` is a single append-only history table for applications *and* rounds.

### 2.1 Tables

```
users
  id, email (unique, lowercased), password_hash, display_name,
  ai_processing_consent_at (nullable)          -- null = never send data to an AI provider

cv_documents                                    -- the original uploaded file, never modified
  id, user_id→users, original_filename, mime_type, size_bytes, sha256, storage_key, uploaded_at
  UNIQUE(user_id, sha256)                       -- same file uploaded twice → reuse

cv_versions                                     -- parsed, user-correctable content
  id, user_id→users, cv_document_id→cv_documents (RESTRICT), label ("Backend v2"),
  version_number INT, raw_text TEXT,
  parse_status (ok|partial|failed), parse_warnings JSONB,
  is_confirmed BOOL                              -- user has reviewed sections
  UNIQUE(user_id, version_number)

cv_sections
  id, cv_version_id→cv_versions (CASCADE),
  section_type (education|skills|experience|internship|projects|certifications|achievements|other|unrecognized),
  heading_text, order_index, char_start, char_end, user_corrected BOOL

cv_passages                                     -- bullets / lines; the unit evidence points to
  id, cv_section_id→cv_sections (CASCADE), cv_version_id→cv_versions (CASCADE),
  text, char_start, char_end, order_index
  CHECK(char_end > char_start)

job_applications
  id, user_id→users, company_name, position_title, job_description TEXT, job_url, source,
  deadline DATE, saved_at, applied_at (nullable),
  cv_version_id→cv_versions (RESTRICT, nullable),  -- a CV version can serve many applications
  status (interested|preparing|applied|in_progress|offer|rejected|withdrawn|closed_unknown),
  notes TEXT, archived_at (nullable)               -- soft archive, never hard delete history

requirement_analyses
  id, application_id→job_applications (CASCADE), cv_version_id→cv_versions (RESTRICT),
  method (rule_engine|ai), jd_sha256, cv_text_sha256, status (complete|failed), created_at
  -- "is this analysis stale?" = hashes differ from current JD/CV

job_requirements
  id, analysis_id→requirement_analyses (CASCADE),
  text, normalized_terms JSONB, jd_char_start, jd_char_end,
  category (technical_skill|tool|experience|education|project|collaboration|responsibility|other),
  importance (required|preferred|uncertain),
  evidence_status (demonstrated|partially_demonstrated|not_found_in_cv|needs_verification),
  evidence_rationale, missing_details, suggested_next_action,
  self_report (unknown|have_not_on_cv|do_not_have|learning),
  origin (rule_engine|ai|user), user_edited BOOL

requirement_evidence                            -- link table
  id, requirement_id→job_requirements (CASCADE), cv_passage_id→cv_passages (CASCADE),
  matched_terms JSONB, relevance_note, origin
  UNIQUE(requirement_id, cv_passage_id)

cv_recommendations
  id, requirement_id→job_requirements (CASCADE, nullable), cv_version_id→cv_versions,
  cv_passage_id→cv_passages (nullable),
  kind (presentation|evidence_gap|potential_capability_gap|unverified_claim),
  original_text, suggested_text, rationale, assumptions JSONB (list of "confirm that…"),
  status (proposed|accepted|edited|rejected), final_text, origin

skill_gaps                                      -- per user, spans applications
  id, user_id→users, skill_name,
  gap_type (knowledge|application|speed|recall|preparation|communication|unclassified),
  importance (high|medium|low), confidence (low|medium|high),
  status (open|improving|resolved|dismissed), priority SMALLINT CHECK 1..5,
  target_date, recommended_action, basis, origin
  UNIQUE(user_id, lower(skill_name))            -- one gap per skill; many sources attach to it

gap_evidence                                    -- why this gap exists / changed (traceability)
  id, skill_gap_id→skill_gaps (CASCADE),
  requirement_id→job_requirements (nullable), question_id→questions (nullable),
  journal_id→journals (nullable), note, basis
  CHECK(at least one of requirement_id, question_id, journal_id, note is not null)

gap_reassessments                               -- reassessment history, append-only
  id, skill_gap_id→skill_gaps (CASCADE), assessed_at,
  previous_status, new_status, confidence, summary,
  task_attempt_id (nullable), question_attempt_id (nullable)

recruitment_rounds
  id, application_id→job_applications (CASCADE), order_index, name,
  round_type (cv_screening|online_assessment|written_exam|technical_interview|hr_interview|managerial_interview|final_decision|other),
  scheduled_at (nullable), confirmation_deadline (nullable),
  status (not_scheduled|upcoming|preparing|completed|awaiting_result|rescheduled|cancelled),
  result (unknown|passed|failed|not_applicable),   -- SEPARATE from status: completed ≠ passed
  follow_up_date, completed_at, links JSONB, notes

recruitment_events                              -- append-only history
  id, user_id→users, application_id→job_applications (CASCADE), round_id→recruitment_rounds (nullable),
  event_type (application_created|application_status_changed|round_created|round_rescheduled|
              round_status_changed|round_result_recorded|note),
  old_value JSONB, new_value JSONB, reason, occurred_at

tasks                                           -- learning AND preparation
  id, user_id→users, kind (learning|preparation),
  title, description, status (planned|in_progress|completed|needs_more_practice),
  priority SMALLINT 1..5, due_date,
  skill_gap_id (nullable), job_requirement_id (nullable),
  application_id (nullable), recruitment_round_id (nullable), question_id (nullable),
  why (text: "generated because requirement X was not_found_in_cv"), origin

task_attempts
  id, task_id→tasks (CASCADE), attempted_at, duration_minutes,
  outcome (struggled|partial|solid), notes

journals
  id, user_id→users, application_id→job_applications (CASCADE), round_id→recruitment_rounds (nullable),
  template (technical_assessment|written_exam|interview|general),
  responses JSONB          -- {prompt_key: answer}, prompts defined in code per template
  interviewer_feedback TEXT, user_interpretation TEXT,   -- kept apart on purpose
  follow_up_actions TEXT, occurred_on DATE

questions
  id, user_id→users, application_id (nullable, SET NULL), round_id (nullable, SET NULL),
  journal_id (nullable, SET NULL),
  text, subject, topic, difficulty (easy|medium|hard|unknown),
  original_answer TEXT,                  -- immutable after creation (edits go to attempts)
  response_quality (confident|partial|could_not_answer|not_attempted),
  time_spent_minutes, confidence SMALLINT 1..5, difficulty_reason,
  verified_solution TEXT, ai_suggestion TEXT,     -- three provenances, three columns
  practice_status (new|to_practice|practicing|comfortable), asked_on DATE
  INDEX on (user_id, topic), GIN trigram/tsvector on text for search

question_attempts
  id, question_id→questions (CASCADE), attempted_at, answer, response_quality,
  time_spent_minutes, confidence, notes
```

### 2.2 Key relationships & constraints, in plain words
- **One CV version → many applications** (`job_applications.cv_version_id`, RESTRICT so a version in
  use can't be deleted).
- **One application → many analyses** (one per CV version/JD revision); the latest is shown, older ones
  stay readable.
- **Requirements belong to an analysis**, which belongs to an application, so a requirement always
  knows its source job.
- **Evidence points at a passage with char offsets** → the UI can highlight the exact CV text.
- **A skill gap is per user, not per job.** "SQL" from three job descriptions is one gap with three
  `gap_evidence` rows — that's what powers "learning priorities shared across roles".
- **History is never overwritten:** rescheduling writes a `recruitment_events` row with old/new dates;
  status changes likewise; `questions.original_answer` never changes; gap changes add a reassessment.
- **Round `status` and `result` are separate columns.** Moving a round to `completed` never touches
  `result` or the application status.

---

## 3. REST API plan

Prefix `/api/v1`. JSON. Errors are always `{"error": {"code": "...", "message": "...", "details": ...}}`.
List endpoints take `limit`/`offset` and return `{items, total}`. All routes except auth require a
session; every query is scoped to the current user (404, not 403, for other users' records).

**P0 — Day 1–2 (core loop)**
```
POST   /auth/register | /auth/login | /auth/logout      GET /auth/me
GET    /applications?status=&q=        POST /applications
GET    /applications/{id}              PATCH /applications/{id}    (status change → event)
POST   /applications/{id}/archive
GET    /applications/{id}/timeline     (events + rounds, chronological)
GET    /applications/{id}/rounds       POST /applications/{id}/rounds
GET    /rounds/{id}                    DELETE /rounds/{id}?reason=   (history + snapshot kept)
PATCH  /rounds/{id}                    (any field; changing scheduled_at records a reschedule with
                                        old+new dates; optional change_reason)
POST   /cv-versions                    (multipart upload → document + version + sections + passages)
GET    /cv-versions                    GET /cv-versions/{id}  (sections + passages)
PATCH  /cv-versions/{id}               (label, is_confirmed)   DELETE /cv-versions/{id} (409 if in use)
PATCH  /cv-versions/{id}/sections/{sid} (correct section type)
GET    /cv-versions/{id}/file          (original file, byte for byte)
POST   /applications/{id}/analyses     (run analysis against application's CV version)
GET    /applications/{id}/analyses     GET /analyses/{id}
GET    /applications/{id}/analyses/latest   (requirements + evidence + coverage + staleness flag)
PATCH  /requirements/{id}              (category/importance/self_report/dismissed; text is not
                                        editable, since evidence offsets point into the JD)
GET    /analyses/{id}/recommendations  PATCH /recommendations/{id}  (accept/edit/reject)
POST   /journals   GET /journals?application_id=   GET/PATCH /journals/{id}
GET    /journal-templates              (prompt definitions per template)
POST   /journals/{id}/questions        (bulk-save questions recorded in a journal)
GET    /questions?q=&company=&position=&round_type=&topic=&difficulty=&response_quality=&practice_status=&from=&to=
GET    /questions/{id}  PATCH /questions/{id}
POST   /questions/{id}/attempts        GET /questions/{id}/attempts
```
**P1 — Day 3 (learning, preparation, dashboard)**
```
GET    /skill-gaps?status=   POST /skill-gaps   PATCH /skill-gaps/{id}
POST   /requirements/{id}/skill-gap    (create/attach gap from requirement; requires self_report or explicit user action)
POST   /questions/{id}/skill-gap       (create/attach gap from a struggled question)
POST   /skill-gaps/{id}/reassessments  GET /skill-gaps/{id}/history
GET    /tasks?kind=&status=&application_id=&round_id=&gap_id=   POST /tasks   PATCH /tasks/{id}
POST   /tasks/{id}/attempts
POST   /applications/{id}/preparation/suggest   (rule-based draft checklist, returned NOT saved; user picks)
GET    /dashboard                      (upcoming rounds, overdue, pending results, follow-ups, top tasks, recent journals)
GET    /insights                       (each: claim, observation_count, source_refs[], basis, sufficient_data bool)
```
**P2 — Day 4 / stretch**
```
PATCH  /users/me/ai-consent
POST   /applications/{id}/analyses?method=ai   (only with consent + configured provider)
GET    /calendar?from=&to=
```

---

## 4. Directory structure

```
careerlens/
├── README.md                 LEARNING_GUIDE.md          docker-compose.yml   .env.example
├── docs/PLAN.md              docs/ARCHITECTURE.md
├── backend/
│   ├── pyproject.toml        alembic.ini
│   ├── alembic/versions/
│   ├── app/
│   │   ├── main.py           # FastAPI app, routers, error handlers
│   │   ├── config.py         # pydantic-settings, reads env
│   │   ├── db.py             # engine, session dependency
│   │   ├── auth.py           # password hashing, session cookie, current_user dependency
│   │   ├── models/           # SQLAlchemy models, one file per domain area
│   │   ├── schemas/          # Pydantic request/response models
│   │   ├── api/              # thin routers: parse → call service → return schema
│   │   ├── services/         # business rules (status/event logic, gap logic, insights)
│   │   ├── analysis/         # pure functions, no DB: cv_parser, jd_extractor, matcher, recommender, skills_taxonomy.json
│   │   ├── ai/               # provider protocol, null provider, one real provider, output validators
│   │   └── storage.py        # file storage for uploaded CVs
│   └── tests/
│       ├── conftest.py       # test DB, transactional fixtures, auth'd client
│       ├── fixtures/         # sample CVs (pdf/docx) and job descriptions we write ourselves
│       └── test_*.py
└── frontend/
    ├── package.json  next.config.ts  (rewrites /api/* → FastAPI, so cookies are same-origin)
    ├── src/app/              # routes: /login, /, /applications, /applications/[id], /cv, /questions, /learning
    ├── src/components/ui/    # shadcn components
    ├── src/components/       # feature components (EvidenceTable, RoundTimeline, JournalForm…)
    └── src/lib/              # api client, generated types, formatters
```

The `analysis/` package is deliberately pure (text in → dataclasses out). It's the most
interesting code to study and the easiest to unit-test.

---

## 5. Dependencies & setup

| Area | Choice | Why |
|---|---|---|
| Python | 3.13 (installed) | Broad library support |
| Python tooling | pip + venv, pinned `requirements*.txt` | Nothing extra to install; easy to read |
| API | FastAPI, Pydantic v2, pydantic-settings | Required stack; auto OpenAPI docs |
| DB | SQLAlchemy 2.x (sync), psycopg 3, Alembic | Sync is simpler to learn and debug; async buys nothing at this scale |
| Auth | pwdlib[argon2] + signed session cookie (itsdangerous) or PyJWT in httpOnly cookie | Minimal, no third-party auth service |
| PDF | pypdf | Pure Python, no system deps on Windows |
| DOCX | python-docx | Standard |
| Matching | rapidfuzz | Fuzzy alias matching for skill terms |
| Tests | pytest, httpx (FastAPI TestClient) | Against a real Postgres test DB, not SQLite (CHECK/JSONB/trigram behave differently) |
| Frontend | Next.js (App Router) + TypeScript, Tailwind, shadcn/ui | Required stack |
| Frontend data | TanStack Query, react-hook-form + zod | Caching/refetch and forms without hand-rolled state |
| API types | openapi-typescript | Frontend types generated from FastAPI's schema — no drift |
| DB runtime | Postgres 16 in Docker Compose | One command; same on any machine |

Exact versions get pinned to the current stable releases when the project is scaffolded (Milestone 1)
and recorded in the lockfiles.

**Setup flow (target):**
```
docker compose up -d db
cd backend && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

---

## 6. Four-day checklist (with acceptance criteria)

### Day 1 — Foundation
- [x] **M1 Scaffold:** repo, Docker Postgres, FastAPI app, config, Alembic baseline, health route, Next.js app with proxy.
  ✅ `GET /api/v1/health` returns DB ok; `alembic upgrade head` on empty DB succeeds; frontend shows health.
  *Done 2026-10-25.* Verified: 4 backend tests pass (health OK, health 503 when DB unreachable, standard
  404/405 error format); health through the Next.js proxy; status page shows "Unavailable" within
  0.1s when Postgres is stopped and recovers on restart, with migration `0001` intact; frontend lint,
  typecheck and production build clean. Added a 5s DB connect timeout after finding that an
  unreachable DB otherwise hangs requests for ~130s on Windows.
- [x] **M2 Auth + users:** register/login/logout/me, cookie session, `current_user` dependency.
  ✅ Tests: unauthenticated → 401. (The "user B gets 404 on user A's application" test moves to M3,
  where applications, the first user-owned records, are created.)
  *Done 2026-10-25.* Database-backed sessions (only the SHA-256 of the token is stored; logout
  deletes the row), Argon2id passwords, httpOnly + SameSite=Lax cookie, same error for unknown email
  and wrong password, `ALLOW_REGISTRATION` switch. 19 auth tests (23 total). Frontend: /login,
  /register, `proxy.ts` redirect for signed-out visitors, account bar with sign-out. Verified in the
  browser: redirect, registration, cookie hidden from JS, wrong-password message, server-side session
  revocation sends the page to /login without a loop, sign-out deletes the session row.
  Known MVP limits: no login rate limiting, no password reset, no email verification.
- [x] **M3 Applications + rounds + events:** CRUD, status changes, round reschedule, timeline.
  ✅ Tests: user B gets 404 (not 403) on user A's application and its rounds.
  ✅ Tests: status change writes event; reschedule keeps old date in history; completing a round leaves `result=unknown` and application status unchanged.
  ✅ Manual: create app in UI, restart backend + DB container, data still there.
  *Done 2026-10-25.* Migration 0003 (job_applications, recruitment_rounds, recruitment_events with
  CHECK constraints on every status/type/result). 39 new tests (62 total), including user isolation
  for applications and rounds; a deliberate removal of the owner filter was confirmed to fail the
  isolation test. Persistence verified through the API (UI arrives in M4): created an application,
  round, reschedule and completion, restarted API + frontend + Postgres, all data and six history
  entries intact. Changes from plan: rescheduling is any PATCH that changes `scheduled_at` (no
  separate endpoint); rounds can be deleted (snapshot kept in history), applications only archived;
  history date-times stored in UTC; `cv_version_id` column deferred to M5 with the CV tables.
- [x] **M4 Frontend shell:** login, applications list, create form, application detail with rounds + timeline.
  *Done 2026-10-25.* TanStack Query for server state (401 anywhere → sign-in), API types generated
  from FastAPI's OpenAPI schema (`npm run gen:api`), app shell with route group `(app)`. Pages:
  list (search, status filter, archived toggle, pagination, deadline warnings; filters in the URL),
  new/edit application, detail (status dialog with reason, rounds with add/edit/delete dialogs,
  separate status and result badges, readable history, archive/restore banner), `/status`.
  Verified in the browser through the API proxy: create → add round → reschedule with reason →
  status change (applied date auto-filled) → edit deadline (only that change recorded) → search,
  filters, archive/restore, unknown-id page; no horizontal scroll at 375px. Screenshots of the list
  and detail pages found and fixed a translucent page background and a borderless outline link.
  Not visually checked: dialogs and the phone layout (the pane couldn't draw in the background).

### Day 2 — CV evidence & journals
- [x] **M5 CV upload & parsing:** magic-byte validation, 5 MB limit, store original, sections + passages, parse warnings, correction UI.
  ✅ Tests: fake PDF (wrong bytes) rejected; DOCX and PDF fixtures produce expected sections; unparseable/empty text → `parse_status=failed` with message.
  *Done 2026-10-25.* Pure parser in `app/analysis/cv_parser.py` (pypdf, python-docx; dictionary of
  ~100 headings plus Word heading styles; bullets and wrapped lines joined; every passage offset
  slices `raw_text` exactly). Migration 0004: cv_documents, cv_versions, cv_sections, cv_passages,
  `job_applications.cv_version_id` (RESTRICT), offset CHECKs, and a hand-written replacement of the
  event-type CHECK for the new `application_cv_changed` (autogenerate can't see it); downgrade tested.
  Upload size enforced twice: Content-Length middleware before the body is read, and the real byte
  count in the route. 38 new tests (100 total), files built in memory, no real CVs in the repo.
  Browser-verified: upload through the form, section correction, mark reviewed, byte-identical
  download, link to an application (history entry), fake-PDF / duplicate / in-use errors.
  Known limits: no OCR; a PDF heading outside the dictionary is merged into the section above
  (sections can be retyped but not split); multi-column PDFs may come out in the wrong order.
- [x] **M6 Requirement extraction + evidence matching (rule engine):**
  *Done 2026-10-25.* `app/analysis/skills.py` (~120 skills with aliases, kinds and families;
  case-sensitive matching for words like Go/Excel/REST), `jd_extractor.py` (posting headings →
  required/preferred/responsibility/ignored; inline words override; "or" → any-of; offsets into the
  JD), `evidence.py` (used in experience/projects → demonstrated; listed only or related family →
  partial; absent → not found, always worded as "doesn't mean you lack it"; soft skills, vague lines
  and unreadable CVs → needs verification; years capped at partial). Migration 0005:
  requirement_analyses (snapshots with JD hash + CV signature for staleness), job_requirements
  (verdict and self_report as separate columns, user_edited, dismissed), requirement_evidence.
  Re-runs carry over self-reports, corrections and dismissals. Coverage = demonstrated required ÷
  required, with its explanation in every response. 37 new tests (137 total). Browser-verified on a
  real run: verdicts, quoted evidence, self-report beside the verdict, stale flag on the application
  page after a JD edit, re-run carrying over input.
  ✅ Tests: fixture JD yields expected required/preferred split; skill in project bullet → `demonstrated`; only in skills list → `partially_demonstrated`; absent → `not_found_in_cv` and **no capability gap created**; vague soft skill → `needs_verification`; evidence links point to real passage offsets.
  ✅ Re-opening the application shows the stored analysis without re-running; changed CV version flags it stale.
- [x] **M7 Recommendations:** template-based, per requirement, 4 kinds, accept/edit/reject.
  ✅ Tests: recommendations never contain numbers not present in source passage; assumptions list populated for rewrites.
  *Done 2026-10-25.* Pure generator `app/analysis/recommendations.py`: presentation rewrites keep the
  original words and add only [bracketed gaps]; listed-only skills → unverified claim (example
  template, or removal if the candidate said they lack it); not found → evidence gap ("Do you have
  X?" / add an example if they have it); potential capability gap **only** on the candidate's own
  "don't have / learning", with no CV change. Change types: rewrite, add bullet, remove/verify,
  no CV change. Migration 0006 `cv_recommendations` (tied to the analysis snapshot; status
  proposed/accepted/edited/rejected; final_text; decided_at). Generated on each analysis run, carried
  over by key, and refreshed for a requirement when its self-report/category/dismissal changes;
  decided suggestions are never removed. Edited text with new numbers gets a `number_warnings` flag.
  30 new tests (167 total), including "accepting everything leaves the CV and file byte-identical".
  Browser-verified: generation, accept, edit with number warning, "to apply" list with unfilled-gap
  warning, suggestions changing after a self-report. Screens not visually checked (pane not drawing).
- [ ] **M8 Journals + question bank:** templates, journal form, save questions, search/filter, attempts.
  ✅ Tests: journal-question association; filters by company/topic/response_quality; attempts preserve original answer.

### Day 3 — Learning, preparation, dashboard
- [ ] **M9 Skill gaps + tasks + attempts + reassessments.**
  ✅ Tests: gap from requirement requires self_report=`do_not_have`/`learning` or explicit action; same skill from two jobs → one gap, two evidence rows; reassessment history ordered and retrievable.
- [ ] **M10 Preparation:** rule-based suggestions from requirements/gaps/projects, labelled "practice question", user saves selected ones to a round.
- [ ] **M11 Dashboard + insights:** upcoming/overdue/pending/follow-ups; insights with observation counts and "not enough data" (< 3 observations) state.
  ✅ Tests: insight with 1 observation reports insufficient data; every insight returns source refs.

### Day 4 — Stabilise & ship
- [ ] **M12** Full journey run-through (acceptance criteria 1–14 below), bug fixes, error/empty/loading states, mobile layout.
- [ ] **M13** Gemini provider (`ai/gemini.py`; free-tier rate limits → retry with backoff, fall back to rule engine): consent gate, structured output, Pydantic validation, citations must be existing passage IDs whose text contains the quote. Tests for malformed output.
- [ ] **M14** README, ARCHITECTURE.md, LEARNING_GUIDE.md; deploy the single Compose stack (frontend + backend + Postgres) if time allows.

### Final acceptance (from the brief)
1 create application · 2 upload CV + JD · 3 inspect requirements & evidence · 4 see 4 evidence states ·
5 truthful recommendations · 6 prioritised gaps · 7 learning + prep tasks · 8 track rounds/deadlines ·
9 journal a round · 10 save questions + original answers · 11 re-attempt questions · 12 track gap
improvement · 13 connected dashboard · 14 persistence across restarts.

---

## 7. Risks & simplifications

| Risk | Mitigation / simplification |
|---|---|
| Rule-based JD extraction is crude | Accept it: deterministic, explainable, testable, and every requirement is user-editable. AI is a later *optional* layer that must pass the same validators. |
| CV layouts vary wildly (columns, tables, scanned PDFs) | Section detection by heading keywords + fallback `unrecognized`; parse_status + warnings; user correction UI. No OCR. |
| Scope is ~10 features in 4 days | Strict P0/P1/P2; Day 3 features are thin CRUD over a well-designed schema. Insights limited to ~5 queries. Calendar view = stretch. |
| Retrofitting auth breaks every query | Auth and `user_id` scoping on Day 1. |
| AI hallucinating evidence | AI may only cite passage IDs; validator checks quote ⊂ passage text; malformed → fallback to rule engine, never partial garbage. |
| Postgres enum migrations are painful | VARCHAR + CHECK constraints. |
| Windows dev environment friction | Docker for Postgres only; pure-Python parsers (no libmagic/poppler). |
| Cross-origin cookies between Next and FastAPI | Next.js rewrites proxy `/api/*` — browser sees one origin. |
| Status logic scattered across routes | All transitions in `services/`, each writing its event in the same DB transaction. |

# CareerLens architecture

How the pieces fit together, and the rules they all follow. For the original
specification and the milestone log see [PLAN.md](PLAN.md); for a guided tour
of the code see [LEARNING_GUIDE.md](LEARNING_GUIDE.md).

## The big picture

```
Browser ──► Next.js (frontend, :3000) ──/api/*──► FastAPI (backend, :8000) ──► PostgreSQL
                                                        │
                                                        ├─► files on disk (uploaded CVs)
                                                        └─► Google Gemini (optional, with consent)
```

- **One origin for the browser.** The browser only ever talks to Next.js. Next forwards `/api/*` to
  the backend (`frontend/next.config.ts`, rewrites resolved at build time from `API_URL`). So the
  session cookie is first-party and there is no CORS setup.
- **The backend owns all data and every rule.** The frontend renders and calls the API; it never
  decides what the CV shows, what counts as a gap or what is overdue.
- **AI is an optional layer.** Everything works with no AI key. When it's used, its output must pass
  the same kind of checks as everything else, or the rule engine's result is kept.

In production (`docker-compose.prod.yml`) a Caddy server sits in front, terminates HTTPS and forwards
to Next.js. Postgres and the backend are not reachable from outside. See [DEPLOY.md](DEPLOY.md).

## Principles that shape the code

1. **Evidence, not judgement.** The app describes what a CV *shows* ("not found in this CV"), never
   what a person can do. Absence from the CV is never treated as a skill gap on its own; a gap needs
   the candidate's own statement or a recorded struggle.
2. **Provenance on everything.** Records say where they came from: `origin` (rule engine, AI, user)
   and, for claims about the candidate, a `basis` (the CV, the job description, the user's own
   statement, a recorded outcome, or a hypothesis). The candidate's own statements are stored next to
   the CV verdict, never instead of it.
3. **History is kept.** Status changes add rows to `recruitment_events`; gap reassessments are
   append-only; an original question answer is immutable; re-running an analysis creates a new one.
4. **No invented content.** CV suggestions only rearrange the candidate's own words and leave
   `[bracketed gaps]` to fill truthfully; practice questions are labelled as such; insights below three
   observations are marked "not enough data"; co-occurrence is never presented as cause.
5. **Every query is scoped to the current user.** Other users' records are a plain 404.

## Backend (`backend/app`)

| Layer | Folder | What lives there |
|---|---|---|
| HTTP | `api/` | Thin FastAPI routers: parse input, call a service, shape the response. `deps.py` provides `DbSession` and `CurrentUser`. |
| Business rules | `services/` | One module per area (applications, rounds, cvs, analyses, recommendations, journals, questions, learning, preparation, dashboard, insights, events, auth). Owns transactions; writes history events in the same transaction as the change. |
| Pure logic | `analysis/` | No database: `cv_parser` (PDF/DOCX → sections and passages), `jd_extractor` (job description → requirements with exact character offsets), `skills` (the skill dictionary), `evidence` (requirement × passages → verdict), `recommendations`, `preparation`. Easy to unit-test. |
| AI | `ai/` | `provider.py` (the `AIProvider` interface and the `get_ai_provider` dependency), `gemini.py` (Google Gemini with retries), `evidence.py` (prompt, output schema, validator). |
| Data | `models/` | SQLAlchemy 2 models. Status-like columns are `VARCHAR` + `CHECK` (`models/enums.py: db_enum`), so adding a value is a small migration. |
| Contracts | `schemas/` | Pydantic v2 request/response models. The frontend's TypeScript types are generated from them. |

Other files: `errors.py` (every error is `{"error": {"code", "message", "details"}}`; validation
details never echo submitted personal data), `storage.py` (uploaded files: on local disk under
`STORAGE_DIR`, or in a private Supabase Storage bucket for serverless hosting, behind the same
`save`/`read`/`delete` functions),
`upload_limit.py` (rejects oversized uploads before reading them), `journal_templates.py` (the
journal prompts per event type), `config.py` (settings from environment variables).

### Authentication

Email and password (Argon2id via `pwdlib`). A session is a random token in an httpOnly, SameSite=Lax
cookie; the database stores only its SHA-256 hash, so a database leak doesn't hand out sessions.
`COOKIE_SECURE=true` in any deployment. Sign-out deletes the session row.

### Data model (22 tables)

```
users ─┬─ user_sessions
       ├─ cv_documents ── cv_versions ── cv_sections ── cv_passages
       ├─ job_applications ─┬─ recruitment_rounds
       │                    ├─ recruitment_events            (append-only history)
       │                    └─ requirement_analyses ─┬─ job_requirements ── requirement_evidence ──► cv_passages
       │                                             └─ cv_recommendations
       ├─ journals ── questions ── question_attempts
       └─ skill_gaps ─┬─ gap_evidence        (requirement / question / journal / note)
                      ├─ gap_reassessments   (append-only; may cite a task or question attempt)
                      └─ tasks ── task_attempts   (learning and preparation tasks share one table)
```

A job application points at the **CV version** that was sent, so a tailored CV for one job never
changes what another job used. An analysis is a snapshot of one job description against one CV
version; hashes of both make it "stale" when either changes.

### Requirement analysis, step by step

1. `jd_extractor` picks requirement lines out of the job description, with exact offsets, category
   and importance (required, preferred, uncertain).
2. `evidence.assess` checks each against the CV's passages: **demonstrated** (shown in use),
   **partly shown** (only named, or partly), **not found in this CV**, or **needs your judgement**.
   Each verdict links the passages it's based on.
3. Optional AI (`?method=ai`): the rule-engine verdicts are the baseline; the AI's verdicts replace
   them only where they pass validation (below). `assessed_by` records who judged each requirement and
   `notes` explains every fallback.
4. `recommendations` turns the verdicts into CV suggestions; earlier decisions are carried over.
5. Coverage = demonstrated required lines ÷ all required lines (responsibilities, preferred,
   uncertain and dismissed lines excluded), explained in the response.

### The AI layer

- **Interface.** `AIProvider.generate_json(system, prompt, schema) -> str`. `get_ai_provider()` returns
  `None` without `GEMINI_API_KEY`; it's a FastAPI dependency, so tests inject a fake.
- **Consent.** `users.ai_processing_consent_at`; no AI call without it (403 `ai_consent_required`).
- **What's sent.** Requirement lines and CV passages under short ids (`r1`, `p1`). The CV's header
  section (name and contact details) is never sent.
- **Validation** (`ai/evidence.py`). A verdict is used only if every cited passage exists, every quote
  appears in its passage, the status is backed by the citations, and no figures appear that aren't in
  the requirement or the cited passages. A failing verdict falls back to the rule engine for that
  requirement; output that isn't valid for the schema falls back entirely.
- **Resilience.** Rate limits (429), server errors and timeouts are retried with exponential backoff;
  after that the analysis uses the rule engine and says why.

## Frontend (`frontend/src`)

- **Next.js 16 App Router.** Signed-in pages live in the `app/(app)` route group, which shares the
  header and tab bar. `app/login`, `app/register` and `app/not-found.tsx` stand alone.
- **Data.** TanStack Query for all server data. Each `lib/<area>.ts` holds the query keys and API
  calls for one area; keys are nested (e.g. analyses under `"applications"`) so invalidating a parent
  refreshes its children. Any 401 sends the user to `/login` and back.
- **Types.** `lib/api-types.ts` is generated from the backend's OpenAPI schema (`npm run gen:api`).
  A backend schema change shows up as TypeScript errors wherever the frontend must follow.
- **Components.** One folder per area (`components/analysis`, `learning`, …) plus `components/ui`
  (shadcn/ui on Base UI). Shared helpers: `FormField`/`readApiError` (422 details → field errors),
  `LoadError` (not found vs couldn't load), `useCloseOnHide` (Next keeps visited pages mounted but
  hidden, so dialogs close themselves when their page is hidden).
- **Look.** "Glass Ops": frosted-glass `surface` panels, a green accent, light or dark from the
  device setting. Depth effects: pages rise into view on navigation (`components/page-transition.tsx`,
  Web Animations, so page state is kept), cards lift on hover, a 3D grid floor drifts behind
  everything. Reduced-motion settings turn all of it off. Touch screens get 44px targets.

## Testing

- **Backend:** pytest against a real PostgreSQL test database (`careerlens_test`), never SQLite, so
  CHECK constraints, JSONB and functional indexes behave as in production. The test run applies the
  real Alembic migrations; each test runs in a transaction that is rolled back. Uploaded files go to
  a temporary folder. Test CVs are generated in code (`tests/cv_files.py`), so no real person's CV
  is in the repository. Key rules (user isolation, "not found ≠ gap", citation checks, consent) were
  confirmed by deliberately breaking them and watching a test fail.
- **Frontend:** TypeScript (`npm run typecheck`), ESLint and a production build; behaviour is checked
  by walking the journey in a browser (see the Milestone 12 entry in PLAN.md).

## Deployment

Two supported shapes, both described step by step in [DEPLOY.md](DEPLOY.md):

- **One server, Docker Compose** (`docker-compose.prod.yml`): `db` (Postgres 16, named volume),
  `backend` (runs `alembic upgrade head`, then uvicorn; CV uploads on a named volume), `frontend`
  (Next.js standalone server) and `caddy` (automatic HTTPS). Configuration comes from `deploy/.env`.
- **Serverless: Vercel + Supabase.** The API and the web app are two Vercel projects; Supabase hosts
  the database and a private bucket for CVs. `DB_SERVERLESS=true` makes each request open its own
  connection through Supabase's pooler without prepared statements; `STORAGE_BACKEND=supabase` moves
  CV files to the bucket; migrations are run from a developer machine. CVs are capped at 4 MB to fit
  Vercel's request size limit.

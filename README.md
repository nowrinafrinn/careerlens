# CareerLens

An evidence-based career intelligence platform. CareerLens connects job-description analysis, CV
evidence, skill gaps, targeted preparation, recruitment tracking, interview journals and a personal
question bank into one feedback loop, and is careful to separate what your CV shows, what you have
confirmed, and what is only an inference.

> **Status:** Milestones 1–8 of 14 are complete: foundation, accounts, applications and recruitment
> rounds with their screens, CV upload with section extraction, requirement-to-CV evidence analysis,
> CV improvement suggestions, and recruitment journals with a personal question bank. See [docs/PLAN.md](docs/PLAN.md) for the
> specification, schema, API plan and checklist.

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, psycopg 3 |
| Database | PostgreSQL 16 (Docker) |
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind CSS 4, shadcn/ui |
| Tests | pytest + FastAPI TestClient against a real Postgres test database |
| AI (later, optional) | Google Gemini behind a replaceable provider interface |

## How the pieces talk

```
Browser ──► Next.js :3000 ──(/api/* rewrite)──► FastAPI :8000 ──► PostgreSQL :5432 (Docker)
```

The browser only ever talks to Next.js. Requests to `/api/*` are forwarded to FastAPI, so the
browser sees a single origin. That keeps login cookies simple and means no CORS configuration.

## Accounts and sign-in

- Passwords are hashed with Argon2id; the plain password is never stored or logged.
- Signing in creates a session row; the browser gets a random token in an `httpOnly`, `SameSite=Lax`
  cookie, and the database stores only the token's SHA-256 hash. Signing out deletes the row, so the
  old cookie stops working everywhere.
- Every API route that touches a user's records takes the `CurrentUser` dependency
  (`backend/app/api/deps.py`) and filters by that user's id.
- `frontend/src/proxy.ts` redirects signed-out visitors to `/login` before the page loads. It only
  checks that a cookie exists; the backend decides whether it is valid.
- For a public deployment set `COOKIE_SECURE=true`, and `ALLOW_REGISTRATION=false` once your own
  account exists.

Not yet implemented: login rate limiting, password reset, email verification.

## Applications, rounds and history

- An **application** has its own status (`interested` → … → `offer` / `rejected` / `withdrawn` /
  `closed_unknown`). Any status can follow any other; the history shows every change.
- Each application has ordered **recruitment rounds**. A round has a **status** (where it is in time:
  `not_scheduled`, `upcoming`, `completed`, …) and a separate **result** (`unknown`, `passed`,
  `failed`). Completing a round never marks it passed, and nothing a round does changes the
  application's status.
- **`recruitment_events`** is append-only. Status, result and date changes each add a row with the
  old and new values and an optional reason, so a rescheduled interview keeps its original date.
  `GET /applications/{id}/timeline` returns it. Date-times in the history are stored in UTC.
- Applications are archived, never deleted. A round created by mistake can be deleted; the deletion
  is itself recorded with a snapshot of the round.

## CVs

- Upload a PDF or DOCX (up to 5 MB) on the CVs page. The file type is decided from the file's
  content, not its name. The original is stored unchanged under `backend/storage/` (git-ignored)
  and can be downloaded again.
- `backend/app/analysis/cv_parser.py` extracts the text and splits it into sections (education,
  skills, experience, projects…) and passages (bullets or lines). Each passage records its
  character offsets in the extracted text, so later features can point at the exact CV text.
- What the parser can't place is shown as **Unrecognized**, never guessed. A section it didn't find
  produces a warning that says so, not a claim that the CV lacks it. You can retype any section and
  mark the version as reviewed.
- Each upload is a numbered version; an application records which version you used.
- Limits: no OCR, so scanned PDFs are saved but marked as unreadable; multi-column layouts may be
  read in the wrong order; sections can be retyped but not split or merged.
- Nothing is sent to an external AI service.

## Requirements and CV evidence

On an application with a job description and a CV version, **Analyse requirements** compares them.
It is rule-based (`backend/app/analysis/`), so nothing is sent to an AI service and every verdict
can be traced back to its rule.

| Verdict | Meaning |
|---|---|
| Demonstrated | The CV shows the skill used in a role, internship or project |
| Partly shown | Only listed (e.g. in Skills), only a related skill is used, or part is missing |
| Not found in this CV | The CV doesn't mention it. **This is not evidence that you lack it** |
| Needs your judgement | Soft skills, years of experience and vague lines can't be settled by text matching |

- Each verdict lists the CV passages it used, with their section and why they count.
- **Your own assessment** ("I have this but it's not on my CV", "I don't have this yet", "I'm
  learning this") is stored next to the verdict and never changes it.
- **Coverage** is demonstrated required requirements ÷ all required requirements. Preferred,
  uncertain, dismissed and responsibility lines are excluded. It describes the CV, not you, and it
  doesn't predict hiring.
- Analyses are snapshots. If the job description, the CV version or its section types change, the
  analysis is marked out of date. Re-running keeps your assessments and corrections.
- The skill dictionary (`backend/app/analysis/skills.py`) only knows the terms listed in it. Add
  missing ones there.

## CV suggestions

Each analysis produces suggestions (Application → CV suggestions), each tied to a requirement and,
where relevant, to the CV passage involved:

| Kind | When |
|---|---|
| Presentation | The skill is shown in use, but the bullet doesn't say what it was for or what came of it |
| Unverified claim | A skill is listed with nothing to back it up (or listed although you said you don't have it) |
| Evidence gap | The CV doesn't show it, and you haven't said, or have said you have it |
| Possible learning goal | Only when **you** said "I don't have this yet" or "I'm learning this". Never a CV change |

- Suggestions never invent experience, results or numbers. Rewrites keep your words and add
  **[bracketed gaps]** for you to fill truthfully or delete. A test checks every suggestion for numbers
  that weren't in the original.
- Each suggestion lists what you must confirm before using it. If your own edit adds a number, the app
  asks you to check it.
- Accept, edit or reject each one. Your uploaded CV is never changed: accepted text is collected under
  **To apply in your CV** for you to copy into your own document.
- Changing your self-assessment on a requirement updates its suggestions. Decisions you've made are
  kept, also across re-runs.

## Journals and the question bank

- After a round, **Write journal** (on the round, or on the application) opens structured prompts for
  that kind of event: technical assessment, written exam, interview or general. The prompts are
  defined in `backend/app/journal_templates.py`.
- **What you were told** (explicit feedback only) and **your interpretation** are separate fields,
  shown separately, so you can always tell what was actually said from what you guessed.
- Questions recorded in a journal go into the **question bank** (Questions in the header), searchable
  by text, company, position, round type, topic, difficulty, outcome, practice status and date.
- A question's **original answer is never edited**. Later tries are saved as attempts and shown
  "then and now", next to the original. A **verified solution** and any future **AI suggestion** are
  kept in their own fields and labelled as such.
- Recording an attempt marks a question as "practising". Only you can mark it "comfortable".

## Prerequisites

- Docker Desktop (running)
- Python 3.12+
- Node.js 22+

## First-time setup

From the repository root (`E:\careerlens`). Commands are for Windows PowerShell.

```bash
docker compose up -d --wait db
```

```bash
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
copy .env.example .env
.venv\Scripts\alembic.exe upgrade head
cd ..
```

```bash
cd frontend
npm install
cd ..
```

## Running in development

Two terminals:

```bash
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm run dev
```

Then open:

- http://localhost:3000: the app (create an account on first visit)
- http://localhost:3000/api/docs: interactive API documentation
- http://localhost:3000/status: API and database status

## Frontend structure

- `src/app/(app)/`: signed-in pages sharing the header layout. `(app)` is a route group and doesn't
  appear in URLs.
- `src/lib/api-types.ts` is **generated** from the backend's OpenAPI schema. After changing a backend
  schema, run `npm run gen:api` (with the backend running) and the TypeScript compiler will point at
  every place in the frontend that needs updating. On Windows the backend's auto-reload sometimes
  misses changes (especially after switching git branches). If new endpoints are missing from the
  generated file, restart the backend and run it again.
- Server data goes through TanStack Query (`src/lib/applications.ts` holds the query keys and API
  calls). Any 401 response sends the user to `/login` and back afterwards.
- Next.js 16 keeps recently visited pages mounted but hidden. Dialogs close themselves when hidden
  (`useCloseOnHide`), and sign-out does a full page load so no previous user's data stays in memory.

## Tests and checks

```bash
cd backend
.venv\Scripts\python.exe -m pytest
```

```bash
cd frontend
npm run lint
npx tsc --noEmit
```

Backend tests run the real Alembic migrations against `careerlens_test` (created automatically the
first time the database container starts) and roll back every test, so they never touch your data.

## Database migrations

```bash
cd backend
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\alembic.exe revision --autogenerate -m "describe the change"
```

Tables are only ever created by migrations, never by `create_all()`. Always read an autogenerated
migration before applying it.

## Data persistence

Postgres data lives in the Docker volume `careerlens_careerlens-pgdata`. It survives container
restarts, `docker compose stop` and `docker compose down`. Only `docker compose down -v` deletes it.

## Repository layout

```
backend/
  app/
    main.py          FastAPI app factory, routers, error handlers
    config.py        settings from environment variables / backend/.env
    db.py            engine and per-request session
    errors.py        the single {"error": {...}} response format
    api/             thin route handlers
    schemas/         Pydantic request/response models
    models/          SQLAlchemy models (Base with constraint naming conventions)
  alembic/           migrations
  tests/
frontend/
  src/app/           routes (App Router)
  src/components/    UI; components/ui holds shadcn components
  src/lib/api.ts     fetch wrapper that understands the API error format
docker/postgres/init SQL run on first database start (creates the test DB)
docs/PLAN.md         specification, schema, API plan, checklist
```

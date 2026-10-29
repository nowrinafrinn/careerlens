# CareerLens

An evidence-based career intelligence platform. CareerLens connects job-description analysis, CV
evidence, skill gaps, targeted preparation, recruitment tracking, interview journals and a personal
question bank into one feedback loop, and is careful to separate what your CV shows, what you have
confirmed, and what is only an inference.

> **Status:** all 14 milestones of the MVP are complete: accounts, applications and recruitment
> rounds, CV upload with section extraction, requirement-to-CV evidence analysis, CV improvement
> suggestions, recruitment journals with a personal question bank, an evidence-based learning plan,
> position-specific preparation, a dashboard with insights, optional AI-assisted analysis with
> Google Gemini, and a production Docker Compose stack.

## Documentation

| Read this | For |
|---|---|
| This README | What the app does, how to run it locally, tests and migrations |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How the pieces fit together and the rules they follow |
| [docs/LEARNING_GUIDE.md](docs/LEARNING_GUIDE.md) | A guided path through the code, with exercises |
| [docs/DEPLOY.md](docs/DEPLOY.md) | Putting it on a server with HTTPS, backups and updates |
| [docs/PLAN.md](docs/PLAN.md) | The original specification and a log of every milestone |

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, psycopg 3 |
| Database | PostgreSQL 16 (Docker) |
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind CSS 4, shadcn/ui |
| Tests | pytest + FastAPI TestClient against a real Postgres test database |
| AI (optional) | Google Gemini (`google-genai`) behind a replaceable provider interface |
| Deployment | Docker Compose (Postgres, API, web app, Caddy for HTTPS), or free on Vercel + Supabase |

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

- Upload a PDF or DOCX (up to 4 MB) on the CVs page. The file type is decided from the file's
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

## Learning plan

- A **skill gap** is per skill, not per job: "SQL" from three applications is one gap with three
  pieces of evidence, which shows how many of your target roles it matters for.
- Gaps only come from evidence you provided: a requirement you marked "I don't have this yet" or
  "I'm learning this", a question you partly answered or couldn't answer, or your own note. A
  requirement your CV simply doesn't mention is **not** enough.
- The **kind of gap** (knowledge, application, speed, recall, preparation, communication) is your
  own diagnosis. CareerLens never infers it from a wrong answer.
- **Learning tasks** link to the gap (and requirement, question or round) that motivated them, with
  logged practice sessions.
- A gap's status changes only through a **reassessment**: new status, confidence, what it's based
  on, and optionally the practice session or question re-attempt that shows it. The history is kept.

## Preparing for a round

**Prepare** (on the application or a round) suggests what to prepare, from your own records:
format tips for the round type, questions about the projects that are your evidence for the job's
skills, topics to review where the CV only names a skill, honest-answer prep where it doesn't show
one, STAR prompts for listed responsibilities, relevant open skill gaps, and past questions you
haven't mastered.

- Every suggestion says **why** it was made and links to its source.
- Generated questions are labelled **practice questions**. CareerLens never claims an employer will
  ask them.
- Suggestions aren't stored. Add the ones you want to the round's **checklist** (preparation tasks),
  or write your own items. It all works without any AI.

## Dashboard and insights

The **dashboard** (`/`) collects what needs you today, using your browser's local date:

- **Needs attention:** application deadlines, rounds and confirmation dates that have passed, and
  overdue tasks.
- **Coming up** (next 14 days): rounds with their preparation progress, and application deadlines.
- **Waiting on results:** completed rounds without a result, and follow-up dates.
- Your applications by status, each analysis's CV coverage and the requirements still waiting for
  your own assessment, open tasks, skill-gap counts, questions to practise and recent journals.
- Closed and archived applications are left out.

**Insights** (`/insights`) are patterns across your records: skills that recur across your target
jobs, required skills your CV doesn't show yet, topics where you recorded difficulty, question topics
that come up in several applications, and gaps you've reassessed.

- Each insight shows its **observation count**, what it's based on (job descriptions, CV analysis,
  your recorded outcomes or your own statements) and links to its source records.
- Below **3 observations** an insight is marked **Not enough data yet**: one event isn't a pattern.
- Things that happened together aren't presented as cause and effect, and rejections aren't used to
  judge your ability.

## Optional AI assistance (Google Gemini)

Everything works without AI. If the server has a Gemini API key, the analysis page also offers
**Analyse with AI**, which asks Gemini to judge the CV evidence for each requirement.

- **Consent first.** The first time, a dialog says exactly what is sent: the job's requirement lines
  and the text of your CV's sections. The top of the CV (name and contact details) is never sent.
  Consent is stored on your account and can be turned off at any time from the same page.
- **Every AI verdict is checked** (`backend/app/ai/evidence.py`). It is used only if each citation
  points at a real passage of this CV and quotes it exactly, its status is backed by its citations
  ("demonstrated" needs a passage showing the skill in use), and it mentions no figures that aren't in
  the requirement or the cited passages. Otherwise that requirement keeps the rule engine's verdict.
- **Nothing silent.** Each AI-judged requirement is marked "AI verdict", and the analysis lists how it
  was made, including every fallback and why. If Gemini is unavailable or rate-limited (retried with
  backoff), the whole analysis uses the rule engine and says so.
- Requirements are still picked out by the rule engine, so their positions in the job description
  stay exact; only the evidence verdicts come from the AI. CV suggestions are built from those verdicts.

To turn it on, get a key at <https://aistudio.google.com/apikey>, add it to `backend/.env` and restart
the backend:

```bash
GEMINI_API_KEY=your-key
```

`GEMINI_MODEL` (default `gemini-2.5-flash`) picks the model. The key stays on the server. On the free
tier Google may use what it receives to improve its products, so test with made-up CVs.

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

If the app suddenly looks unstyled or out of date after a `npm run build`, or edits stop showing up,
the dev server's cache is stale. Stop `npm run dev`, delete the cache in `frontend/`, and start it
again:

```bash
rm -rf .next/dev
```

## Look, phones and accessibility

- Light or dark follows the device setting. Panels are frosted glass (`surface` in `globals.css`);
  content cards lift toward you on hover, each page rises into view on navigation, and a 3D grid
  floor drifts behind everything. All motion stops when the device asks for reduced motion.
- Below 1024px wide the header's links move to a floating tab bar at the bottom (CVs becomes an
  icon in the header).
- On touch screens every button, input and select is at least 44px tall, and small text links get
  a 44px tap area (`tap` in `globals.css`) without changing their look with a mouse.
- A missing record shows "not found" with a way back; an unreachable backend shows a "couldn't be
  loaded" message instead of an empty page.

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
cd backend
.venv\Scripts\python.exe -m ruff check .
```

```bash
cd frontend
npm run lint
npx tsc --noEmit
```

Backend tests run the real Alembic migrations against `careerlens_test` (created automatically the
first time the database container starts) and roll back every test, so they never touch your data.
Ruff checks for unused imports and variables and similar mistakes.

**On GitHub** the same checks run automatically on every push to `main` and every pull request
(`.github/workflows/ci.yml`): backend Ruff and pytest against a PostgreSQL service, frontend lint,
build and typecheck, and a build of both production Docker images. Results show on the repository's
**Actions** tab and as a tick or cross next to each commit.

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

## Deployment

The production stack is `docker-compose.prod.yml`: PostgreSQL, the API, the web app and Caddy for
automatic HTTPS, configured from `deploy/.env`. On a server with Docker and a domain pointing at it:

```bash
cp deploy/.env.example deploy/.env
```

```bash
docker compose -f docker-compose.prod.yml --env-file deploy/.env up -d --build
```

Full guide, including backups, updates and a local trial run: [docs/DEPLOY.md](docs/DEPLOY.md).

## Repository layout

```
backend/
  app/
    main.py          FastAPI app factory, routers, error handlers
    config.py        settings from environment variables / backend/.env
    db.py            engine and per-request session
    errors.py        the single {"error": {...}} response format
    api/             thin route handlers
    services/        business rules and transactions, one module per area
    analysis/        pure logic: CV parsing, requirement extraction, evidence, suggestions
    ai/              optional AI: provider interface, Gemini, output validation
    schemas/         Pydantic request/response models
    models/          SQLAlchemy models (Base with constraint naming conventions)
  alembic/           migrations
  tests/
  Dockerfile         production API image
frontend/
  src/app/           routes (App Router)
  src/components/    UI; components/ui holds shadcn components
  src/lib/           API calls and query keys per area; api-types.ts is generated
  Dockerfile         production web image (Next.js standalone)
deploy/              Caddyfile and the production .env example
docker/postgres/init SQL run on first database start (creates the test DB)
docker-compose.yml       development: PostgreSQL only
docker-compose.prod.yml  production: the whole stack
docs/                architecture, learning guide, deployment, plan
```

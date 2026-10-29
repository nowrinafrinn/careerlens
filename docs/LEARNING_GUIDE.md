# Learning guide: reading the CareerLens code

A suggested path through the codebase, from the outside in. Each stop names the
files to open and what to notice. Have the app running (see the README) so you
can click the thing you're reading about.

For the overall structure, read [ARCHITECTURE.md](ARCHITECTURE.md) first (ten
minutes). For why things were decided, [PLAN.md](PLAN.md) has the specification
and a log of every milestone.

---

## 1. Start the app and look around (15 min)

Create an account, upload a CV, add an application with a job description, and press
**Analyse requirements**. Keep that page open: the next three stops follow that one click.

Also open <http://localhost:3000/api/docs>, the interactive API documentation FastAPI
generates from the code. Every endpoint below is listed there and can be tried in the browser.

## 2. Follow one request end to end (45 min)

**The button.** `frontend/src/components/analysis/analysis-view.tsx`
- `useMutation({ mutationFn: () => runAnalysis(id) })`: TanStack Query runs the request and
  tracks its loading and error state. On success, `setQueryData` puts the new analysis straight
  into the cache, so the page updates without another request.
- `runAnalysis` is in `frontend/src/lib/analysis.ts`. Every area has a file like this: the API
  calls plus the *query keys* that identify cached data.

**The fetch.** `frontend/src/lib/api.ts`
- `apiFetch` calls `/api/v1/...` on the *same origin*. Next.js forwards it to the backend
  (`frontend/next.config.ts`, `rewrites`). Notice there's no URL for the backend in the
  browser code at all.
- A non-2xx response becomes an `ApiError` with `status`, `code` and `message`. Search the
  frontend for `instanceof ApiError` to see how pages react to specific errors.

**The route.** `backend/app/api/analyses.py` → `run_analysis`
- Routers are deliberately thin. `user: CurrentUser` and `db: DbSession` are FastAPI
  *dependencies* (`backend/app/api/deps.py`): FastAPI runs them first and passes the results in.
  `CurrentUser` reads the session cookie and returns 401 if it's missing or expired.
- `provider: ... Depends(get_ai_provider)` is the same idea. Tests replace it with a fake, which
  is why no test ever calls a real AI service.

**The service.** `backend/app/services/analyses.py` → `run_analysis`
- Ownership first: `get_application(db, user, id)` only finds the application if it belongs to
  this user, otherwise 404. Every service does this; it's how one user can never see another's data.
- Then the pure functions do the work (`extract_requirements`, `assess`), the results become
  model objects, and **one `db.commit()`** saves everything together.
- `carried` is how a re-run keeps what you told it last time (your own assessments, dismissed lines).

**The logic.** `backend/app/analysis/jd_extractor.py`, `evidence.py`, `skills.py`
- No database, no HTTP: plain functions in, dataclasses out. That's why they're easy to test
  (`backend/tests/test_requirement_analysis.py`).
- In `evidence.py`, read how a verdict is chosen and how the wording avoids judging the person
  ("This CV doesn't show…", never "you lack…").

**Back in the browser.** `frontend/src/components/analysis/requirement-card.tsx` renders one
requirement. The *self-report* dropdown (`updateRequirement`) stores what *you* say next to what the
CV shows; it never overwrites the verdict.

> **Exercise.** Add a skill to `backend/app/analysis/skills.py` (say, `_s("Svelte Kit", kind="tool",
> family="frontend_framework")`), add it to a job description, and run the analysis again. Then
> write a test in `test_requirement_analysis.py` that proves it's recognised.

## 3. The data model (30 min)

Open `backend/app/models/`. Read `application.py` and `analysis.py` with the diagram in
ARCHITECTURE.md beside you.

- `Mapped[...]` and `mapped_column(...)` are SQLAlchemy 2's typed style. `relationship(...)` lets
  you write `application.rounds` instead of a query.
- Status columns use `db_enum(...)` (`models/enums.py`): stored as text with a `CHECK` constraint,
  so the database itself refuses a value that isn't allowed.
- `recruitment_events` is append-only history. Find where a status change writes one:
  `backend/app/services/events.py` and its callers.

**Migrations.** `backend/alembic/versions/` holds one file per schema change, applied in order.
Compare a model change with its migration (for example `0009_ai_assessment_notes.py`). Note the
explicit `CHECK` constraint there: Alembic's autogenerate drafts a migration, but you always read
and fix it before running it.

> **Exercise.** Run `alembic history` in `backend/`, then `alembic downgrade -1` and
> `alembic upgrade head` on your dev database, and check the column appears and disappears.

## 4. Tests: how the rules are proven (30 min)

Open `backend/tests/conftest.py`.

- Tests run against a real PostgreSQL database (`careerlens_test`) after applying the real
  migrations, so a test failing on a constraint means the constraint works.
- Each test runs inside a transaction that is rolled back at the end: tests never see each
  other's data, and nothing needs cleaning up.
- `ada` is a client already signed in as a fresh user; `sign_up` and `act_as` let a test switch
  between two users. Search for `other_users_cannot` to see the isolation tests.

Then read `backend/tests/test_ai.py`. It shows how to test code that would normally call an
external service: a `FakeProvider` that answers the *real prompt*, including deliberately wrong
answers, to prove they're caught.

> **Exercise (a "mutation test").** In `backend/app/ai/evidence.py`, change
> `if len(quote) < 4 or quote not in _normalise(passage.text):` to `if False:` and run
> `pytest tests/test_ai.py`. A test should fail. Undo the change. If no test failed, the rule
> wasn't really tested. This is how the key rules in this project were checked.

## 5. Authentication (20 min)

`backend/app/services/auth.py` and `backend/app/api/auth.py`.

- Passwords are hashed with Argon2id (`pwdlib`); the plain password is never stored.
- A session is a random token in an httpOnly cookie (JavaScript can't read it). The database
  stores only the token's SHA-256 hash. Ask yourself why that matters if the database leaked.
- Sign-out deletes the session row, so the cookie is useless afterwards.
- On the frontend, `frontend/src/components/providers.tsx` sends you to `/login` on any 401.

## 6. The frontend shell (30 min)

- `frontend/src/app/layout.tsx` (fonts, theme colours) and `app/(app)/layout.tsx` (header, tab
  bar, the page-transition component). `(app)` is a *route group*: it shares a layout without
  adding to the URL.
- `frontend/src/app/globals.css`: the colour tokens for light and dark (`:root` and the
  `prefers-color-scheme: dark` block), the `surface` glass panel, the `tap` touch-target helper,
  and the background layers. Change `--primary` and watch the whole app follow.
- `frontend/src/components/page-transition.tsx`: why it animates with the Web Animations API on
  every URL change instead of remounting the page (the comment explains).
- Generated types: run `npm run gen:api` with the backend running, then open
  `frontend/src/lib/api-types.ts`. Change a field in a backend schema, regenerate, and run
  `npm run typecheck`: TypeScript lists every place the frontend must follow.

## 7. The optional AI layer (30 min)

Read in this order: `backend/app/ai/provider.py` (the interface), `ai/evidence.py` (prompt,
schema, validator: the important part), `ai/gemini.py` (calling Google with retries), then the
`_apply_ai` function in `services/analyses.py`.

The design question to think about: *how do you use a model that can make things up in an app
whose whole point is not making things up?* The answer here is that the model may only cite
passages by id, its quotes are checked against those passages, and anything that fails falls back
to the deterministic rule engine, with a note saying so.

## 8. Ideas to try next

- **Small:** add a journal template (`backend/app/journal_templates.py`) for a "group exercise"
  round, with its prompts.
- **Medium:** add a filter to the question bank (`services/questions.py` → `search`, then the
  filters in `components/questions/question-bank.tsx`).
- **Bigger:** a new insight rule in `backend/app/services/insights.py`, for example "the round
  types where you most often record difficulty". Keep the rules: an observation count, a basis,
  "not enough data" below three, and no cause-and-effect claims.

## Glossary

| Term | Meaning here |
|---|---|
| Passage | One block of CV text (a bullet, a line) inside a section; evidence links point at passages. |
| Evidence status | What the CV shows for a requirement: demonstrated, partly shown, not found, needs your judgement. |
| Self-report | What the candidate says about a requirement, stored beside the CV verdict. |
| Skill gap | A skill to work on, created only from evidence: your own statement, a recorded struggle, or your note. |
| Reassessment | A dated, append-only judgement of where a gap stands, ideally citing a practice attempt. |
| Basis / origin | Where a claim comes from (CV, job description, your statement, a recorded outcome, a hypothesis) / who produced a record (rule engine, AI, you). |
| Stale analysis | An analysis whose job description or CV version has changed since it ran. |

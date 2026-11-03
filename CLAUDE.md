# ReachAI: guide for coding agents

ReachAI is an end-to-end creator marketing app for startup and solo founders. It finds the creators who will convert, shows a fair price for each one, runs outreach, tracks posts and results, and records payments.

## Read these first, in this order
1. **`docs/ROADMAP.md`**: every feature, its status (done / in progress / next / later), where its spec is, and which files it touches. **Start here. Pick the first `next` item unless the user says otherwise.**
2. **`docs/TECHNICAL_SPEC.md`**: the full design. Each roadmap item links to its section (§).
3. `backend/OUTREACH_EVALUATION.md`: how the outreach eval suite works.

## Keep the roadmap true (required)
- When you **start** an item, set its status to `in progress` and add your branch name.
- When you **finish**, set it to `done`, list the main files, and note anything left over as a new item.
- If you change a design decision, update the spec section **and** the decisions table in spec §0 in the same commit.
- Never leave the roadmap describing work that isn't in the code.

## Repo map
```
backend/                 FastAPI + LangGraph + Inngest (Python)
  app/main.py            FastAPI app, Inngest endpoint
  app/api/routes/        campaign.py, outreach.py, saved_lead.py
  app/my_agent/          CURRENT YouTube discovery graph (to be replaced by app/discovery + app/platforms)
  app/outreach/          Pitch generation graph (generate → validate → repair → collect)
  app/workflow/runtime.py, app/outreach/runtime.py   Run graphs with Postgres checkpointer + Inngest Realtime events
  app/inngest/           Inngest client + functions (campaign/run, outreach/run)
  app/models/            SQLAlchemy models; migrations in alembic/versions/
  app/core/model.py      CURRENT hard-coded Gemini model (to be replaced by app/llm/)
  tests/evals/           Outreach tests (deterministic) + LangSmith eval runner
frontend/                Next.js (App Router) + Clerk + Zustand + Inngest Realtime
  app/campaign/[id]/     details, leads, saved, outreach pages
  app/ListOfInfluencer/  results table + detail sheet
  components/            UI (shadcn-style in components/ui)
docs/                    ROADMAP.md, TECHNICAL_SPEC.md
```

## Run and test
- Backend dev: `cd backend && make dev` (runs migrations, uvicorn on :8000, and the Inngest dev server).
- Backend tests: `cd backend && pytest tests -q`. Tests must not call live APIs; use recorded fixtures.
- Outreach evals (LangSmith, live LLM): `cd backend && python -m tests.evals.runner --experiment-prefix <name>`.
- Frontend: `cd frontend && npm run dev`, lint with `npm run lint`.
- Migrations: `cd backend && alembic revision --autogenerate -m "<what>"`, then `alembic upgrade head`.

## Architecture rules (do not break these)
1. **Cheap first, expensive last.** Code/API → statistics/ML → Jev → code scoring → LLM. The LLM only sees the final shortlist.
2. **Numbers live in code, never in an LLM or Jev.** Metrics, scoring, money and dates are all computed in code.
3. **Judgments go to Jev** (TypeSafe AI): yes/no, labels, scales. One request per item with all its questions. Questions, thresholds and weights live in `app/judge/constants.py` and `questions.py` only.
4. **LLMs only write text people read** (strategy, briefs, pitches, replies), and only through `app/llm/client.py` with a named route. Never import a provider SDK in a node.
5. **Every platform plugs in through the adapter interface** (`app/platforms/base.py`) and returns `CreatorProfile`. Shared nodes never contain platform-specific code.
6. **Every paid external call logs a `cost_events` row.** A run never exceeds its credit reservation.
7. **Untrusted text** (bios, posts, replies) goes in its own state field; nothing a model says can trigger a send or a payment on its own.
8. **Secrets come from env vars only.** Never print, log or commit keys.

## Conventions
- **Branches:** short, plain, and named after the work: `shared-core`, `x-discovery`, `outreach-inbox`. No prefixes or random suffixes.
- **Commits and PRs:** one short line saying what changed, in plain words ("Add creator database and cache"). A short body only if needed.
- Python: async where I/O-bound, Pydantic for schemas, type hints. Keep config in constants modules, not inline.
- Ask the user before changing a decision in spec §0, adding a paid vendor, or doing anything that sends messages or moves money.

# ReachAI: guide for coding agents

ReachAI is an end-to-end creator marketing app for startup and solo founders. It finds the creators who will convert, shows a fair price for each one, runs outreach, tracks posts and results, and records payments.

## Read these first, in this order
1. **`docs/ROADMAP.md`**: every feature, its status (done / in progress / next / later), where its spec is, and which files it touches. **Start here. Pick the first `next` item unless the user says otherwise.**
2. **`docs/TECHNICAL_SPEC.md`**: the full design. Each roadmap item links to its section (§).
3. `backend/OUTREACH_EVALUATION.md`: how the outreach eval suite works.

## Keep the user docs true (required)
The public docs live in `frontend/content/docs/*.mdx` (Fumadocs, served at `/docs`, linked from the in-app navbar).
- **Every time you ship a user-visible change, update the matching docs page and add an entry to `frontend/content/docs/changelog.mdx`** (newest date at the top, plain words, what changed for the user).
- New page? Add it to `frontend/content/docs/meta.json` so it appears in the sidebar.
- Only document what actually works. Things that are built but not wired in go under "Behind the scenes" or "Coming soon", never as shipped.
- Run `cd frontend && npm run build` to check the docs compile.

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
  app/discovery/         Discovery graph (graph.py, nodes.py), runtime (run/resume), brief, prompts, limits
  app/platforms/         Platform adapters (base.py interface, youtube.py); each returns CreatorProfile
  app/metrics/, app/judge/   Numbers in code; Jev questions, weights and scoring
  app/creators/          Creator database (repository.py) and the nightly YouTube refresh (refresh.py)
  app/llm/               LLM client with named routes and fallback; embeddings
  app/outreach/          Pitch generation graph (generate → validate → repair → collect)
  app/outreach/runtime.py   Runs the outreach graph with Postgres checkpointer + Inngest Realtime events
  app/inngest/           Inngest client + functions (campaign/run, outreach/run, nightly refresh)
  app/models/            SQLAlchemy models; migrations in alembic/versions/
  app/core/model.py      Hard-coded Gemini model, still used by outreach only (moves to app/llm: K2)
  tests/evals/           Outreach tests (deterministic) + LangSmith eval runner
frontend/                Next.js (App Router) + Clerk + Zustand + Inngest Realtime
  app/campaign/[id]/     details, leads, saved, outreach pages
  app/ListOfInfluencer/  results table + detail sheet
  components/            UI (shadcn-style in components/ui)
docs/                    ROADMAP.md, TECHNICAL_SPEC.md (internal)
frontend/content/docs/   Public user docs (MDX, served at /docs)
```

## Run and test
- Backend dev: `cd backend && make dev` (runs migrations, uvicorn on :8000, and the Inngest dev server).
- Backend tests: `cd backend && pip install -r requirements-dev.txt && pytest tests -q`. Tests must not call live APIs; use recorded fixtures. Test-only packages go in `requirements-dev.txt`, never `requirements.txt` (it's what Vercel deploys, and the bundle is already near the size limit).
- Creator-database tests also run on real Postgres + pgvector when `PG_TEST_URL` points at a **throwaway** database (it's wiped): `PG_TEST_URL=postgresql+asyncpg://postgres@localhost:5433/reachai_unit pytest tests/creators`. Without it they run on SQLite only.
- Check migrations against a real database with `alembic upgrade head` then `alembic check` (models and database must match).
- Outreach evals (LangSmith, live LLM): `cd backend && python -m tests.evals.runner --experiment-prefix <name>`.
- Frontend: `cd frontend && npm run dev`. **Before pushing any frontend change, run `npx tsc --noEmit` and `npm run build`**: Vercel fails the whole deploy on a single TypeScript error.
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
- **No AI attribution anywhere:** no `Co-Authored-By` or session trailers in commits, no "generated by" footers in PRs, comments or docs, and no tool or assistant names in branch names.
- Python: async where I/O-bound, Pydantic for schemas, type hints. Keep config in constants modules, not inline.
- Ask the user before changing a decision in spec §0, adding a paid vendor, or doing anything that sends messages or moves money.

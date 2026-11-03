# ReachAI roadmap

The single source of truth for **what exists, what's being built, and what's next**.
Full designs are in `docs/TECHNICAL_SPEC.md` (linked as §). Agents: update this file whenever you start or finish an item (see `CLAUDE.md`).

**Status:** `done` · `in progress` · `next` (ready to build, in order) · `later` (designed, not yet scheduled) · `idea` (not designed)

---

## Already built
| ID | Feature | Where |
|---|---|---|
| B1 | YouTube discovery graph (strategy → keywords → search → filter → enrich → semantic → LLM rerank → score → reasoning) | `backend/app/my_agent/` |
| B2 | Durable runs: Inngest functions, Postgres checkpointer, realtime stage events | `backend/app/inngest/`, `backend/app/workflow/runtime.py` |
| B3 | Campaign CRUD, saved leads, auth (Clerk) | `backend/app/api/routes/`, `backend/app/auth/` |
| B4 | Pitch generation graph (fan-out per creator, rule validation, 1 repair, cache) | `backend/app/outreach/` |
| B5 | Outreach evals (deterministic tests + LangSmith runner) | `backend/tests/evals/`, `backend/OUTREACH_EVALUATION.md` |
| B6 | Frontend: brief form, live workflow status, results table and detail sheet, saved leads, outreach page, CSV export (Instantly/Smartlead) | `frontend/app/`, `frontend/components/` |

Known gaps in what's built:
- Email and socials are taken from the first regex match (spec §7, table at the top).
- `users.credits` and `Transaction` are unused.
- Models are hard-coded to Gemini.
- The YouTube quota caps us at ~10 runs/day.

---

## Phase 0: Foundations · §3
| ID | Feature | Status | Spec | Main files |
|---|---|---|---|---|
| F0.1 | LLM gateway wrapper with named routes + fallbacks (LangSmith LLM Gateway, `LLM_BACKEND` switch) | done (`foundations`) | §3.1–3.2 | `app/llm/client.py`, `app/llm/routes.py`, `tests/foundations/test_llm_client.py` |
| F0.2 | Jev client (pinned model, ≤ 8 workers, retry policy, LLM fallback) | done (`foundations`) | §3.3 | `app/judge/client.py`, `tests/foundations/test_judge_client.py` |
| F0.3 | Cost logging (`cost_events`) for every paid call | done (`foundations`) | §5.2 | `app/billing/costs.py`, `app/models/cost_event.py`, migration `c3f1a9d4e2b0` |
| F0.4 | Config/env additions + `.env.example` update | done (`foundations`) | §3.4 | `app/core/config.py`, `backend/.env.example` |
| F0.5 | Postgres cache helper (`cached()`), one `cache_entries` table with namespaces (`search`, `llm`) | done (`foundations`) | §4.14 | `app/discovery/cache.py`, `app/models/cache_entry.py`, migration `c3f1a9d4e2b0` |
| F0.6 | Run execution: `discovery/run` + `discovery/platform` Inngest functions with steps, `run_candidates` / `run_strategy` tables, concurrency keys, limits module | next | §4.14 | `app/inngest/discovery.py`, `app/discovery/limits.py` |

## Phase 1: Shared core + lead generation · §4
| ID | Feature | Status | Spec | Main files |
|---|---|---|---|---|
| F1.1 | `CreatorProfile` + `Post` types | next | §4.1 | `app/platforms/base.py` |
| F1.2 | Platform adapter interface | next | §4.2 | `app/platforms/base.py` |
| F1.3 | Creator DB: `creators`, `creator_snapshots`, `creator_judgments`, `creator_persons`, `person_links` + pgvector | next | §4.4, §4.9 | `app/models/creator.py`, migration, `app/creators/repository.py` |
| F1.4 | Caches: profile (7 d), search results (24–72 h), embeddings + Jev answers by content hash | next | §4.4, §4.11 | `app/creators/`, `app/discovery/cache.py` |
| F1.5 | Metrics: robust stats, momentum, outperformance, per-platform percentiles, IsolationForest anomaly | next | §4.5 | `app/metrics/*` |
| F1.6 | Jev judging questions + scoring combine | next | §4.6–4.7 | `app/judge/questions.py`, `constants.py`, `combine.py` |
| F1.7 | Generic discovery graph (strategy → ladder sourcing → filter → fetch → metrics → recall → judge → score → brief) | next | §4.3 | `app/discovery/graph.py`, `nodes/*` |
| F1.8 | Platform selection (preset + Jev check + user toggle) and discovery ladder with probe-then-expand | next | §4.9 | `app/discovery/ladder.py` |
| F1.9 | YouTube adapter on the core (+ recent-video trend search, quota discipline); parity test against B1 | next | §4.8 | `app/platforms/youtube.py` |
| F1.10 | Streaming results per rung (Inngest Realtime `leads` topic) | next | §4.12 | `app/workflow/runtime.py`, frontend results |
| F1.11 | YouTube 30-day data refresh/delete job | next | §4.4 | `app/creators/refresh.py`, Inngest cron |
| F1.12 | Frontend: platform toggles, badges (rising, trend, suspicious), score breakdown, credit estimate | next | §4.13 | `frontend/components/MultiPlatform.tsx`, `frontend/app/ListOfInfluencer/*` |
| F1.13 | Remove `app/my_agent/` and `app/core/model.py` after parity | later | §13 file map | — |
| F1.14 | Recall benchmark (ladder vs full search, target ≥ 90%) | later | §4.9 | `tests/benchmarks/` |

## Phase 2: Billing · §5
| ID | Feature | Status | Spec | Main files |
|---|---|---|---|---|
| F2.1 | Credits ledger + reservations (reserve → commit/release) | later | §5.2 | `app/billing/ledger.py` |
| F2.2 | Plans + credit costs per action | later | §5.1 | `app/billing/plans.py` |
| F2.3 | Cashfree subscriptions, top-ups, webhooks | later | §5.3 | `app/billing/cashfree.py`, `/webhooks/cashfree` |
| F2.4 | Billing page + credits pill | later | §5.3 | `frontend/app/billing`, `Header.tsx` |

## Phases 3–5: New platforms · §6
| ID | Feature | Status | Spec |
|---|---|---|---|
| F3.1 | X adapter (third-party provider, official API switch) | later | §6.1 |
| F4.1 | Instagram adapter (Apify) | later | §6.2 |
| F5.1 | LinkedIn adapter (public post search + pasted URLs) | later | §6.3 |

## Phase 6: Outreach loop · §7
| ID | Feature | Status | Spec |
|---|---|---|---|
| F6.1 | Identity: email ranking, sponsor blocklist, Jev pick, verification, first name, contact ledger, suppression list | later | §7.1 |
| F6.2 | Creator dossier | later | §7.2 |
| F6.3 | Primary channel per creator | later | §7.3 |
| F6.4 | Pitch quality: founder voice, soft vs offer A/B, plain-text first email | later | §7.4 |
| F6.5 | Connected inbox (Unipile) + sending guardrails + approval rule | later | §7.5 |
| F6.6 | Claim check | later | §7.6 |
| F6.7 | Follow-up sequences (Inngest) | later | §7.7 |
| F6.8 | Review queue UI | later | §7.8 |
| F6.9 | Inbox + reply classification | later | §7.9 |
| F6.10 | Assisted DMs | later | §7.10 |
| F6.11 | Reply-rate analytics | later | §7.11 |

## Phase 7: Deals, tracking, payments · §8
| ID | Feature | Status | Spec |
|---|---|---|---|
| F7.1 | Deal record + events + pipeline board | later | §8.1, §8.5 |
| F7.2 | Brief, contract, creator portal, draft review | later | §8.2 |
| F7.3 | Live detection + post checklist + alerts | later | §8.3 |
| F7.4 | Snapshots, own short links, conversions (promo codes, snippet, server event) | later | §8.4 |
| F7.5 | Results UI | later | §8.5 |
| F7.6 | Pay-on-proof requests, mark paid, reminders, tax-ID collection | later | §8.6 |
| F7.7 | Fair range, add-ons, deal type suggestion, negotiation helper, budget planner | later | §8.7 |
| F7.8 | Extra sources: lookalikes, competitor sponsors, founder followers, pre-warmed niches | later | §4.10 |

## Phase 8: Learning · §9
| ID | Feature | Status | Spec |
|---|---|---|---|
| F8.1 | Learned ranker (LightGBM LambdaRank) | later | §9 |
| F8.2 | Pricing model from agreed rates | later | §9 |
| F8.3 | Product event tracking + dashboards (needed from Phase 1) | later | §11 |

---

## Known issues
| ID | Issue | Status |
|---|---|---|
| K1 | `tests/evals/test_evaluators.py::test_deterministic_evaluators_accept_valid_bundle` fails on `main`: its sample pitch has no "collaboration"/"partnership" wording, which the evaluator now requires. Fix the test fixture, not the evaluator | next |
| K2 | Old pipeline nodes still call `app/core/model.py` directly; they move to `app/llm` as part of F1.7/F1.9 | later |
| K3 | Route models for `strategy`, `pitch`, `reply` are placeholders (current Gemini first); pick them with the LangSmith evals | next |

## Open questions waiting on the user
- `TYPESAFE_API_KEY` must be added in the environment settings before testing Jev live.
- Vendor prices in the spec come from third-party sources; confirm before launch.

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

## Docs
| ID | Feature | Status | Main files |
|---|---|---|---|
| D2 | Public demo campaign at `/demo` (saved real brief + 7 leads, emails removed, sample pitches checked by the real validator in `tests/test_demo_data.py`) and a temporary "Coming soon" landing page with sign-up, log-in, demo and docs links | done (`landing-and-demo`) | `frontend/app/demo/`, `frontend/data/demo/`, `frontend/app/page.tsx` |
| D1 | Public docs site (Fumadocs at `/docs`): welcome, getting started, writing a brief, results, outreach, FAQ, how it works, changelog; search; Docs link in the in-app navbar. Next.js 16.1→16.2 and Tailwind 4.1→4.3 upgrades were needed | done (`docs-site`) | `frontend/content/docs/`, `frontend/app/docs/`, `frontend/lib/source.ts`, `frontend/source.config.ts` |

## Phase 0: Foundations · §3
| ID | Feature | Status | Spec | Main files |
|---|---|---|---|---|
| F0.1 | LLM gateway wrapper with named routes + fallbacks (LangSmith LLM Gateway, `LLM_BACKEND` switch) | done (`foundations`) | §3.1–3.2 | `app/llm/client.py`, `app/llm/routes.py`, `tests/foundations/test_llm_client.py` |
| F0.2 | Jev client (pinned model, ≤ 8 workers, retry policy, LLM fallback) | done (`foundations`) | §3.3 | `app/judge/client.py`, `tests/foundations/test_judge_client.py` |
| F0.3 | Cost logging (`cost_events`) for every paid call | done (`foundations`) | §5.2 | `app/billing/costs.py`, `app/models/cost_event.py`, migration `c3f1a9d4e2b0` |
| F0.4 | Config/env additions + `.env.example` update | done (`foundations`) | §3.4 | `app/core/config.py`, `backend/.env.example` |
| F0.5 | Postgres cache helper (`cached()`), one `cache_entries` table with namespaces (`search`, `llm`) | done (`foundations`) | §4.14 | `app/discovery/cache.py`, `app/models/cache_entry.py`, migration `c3f1a9d4e2b0` |
| F0.6 | Run execution: Inngest function running/resuming the LangGraph discovery graph, `run_candidates` / `run_strategy` tables, concurrency/singleton/idempotency/cancel, limits module | done (`run-engine`) | §4.14 | `app/discovery/runtime.py`, `app/inngest/functions.py`, `app/discovery/limits.py`, `app/discovery/node_cache.py`, `app/models/discovery_run.py` (migration `e4b8c1d6a2f9`), `tests/discovery/test_runtime.py` |

## Phase 1: Shared core + lead generation · §4
**Decisions (Nov 3):**
- **The new pipeline replaces the old one (decided Nov 4)**, after the 3-brief comparison; it's tuned in place. The old pipeline and its switch are removed (F1.13).
- Database: Neon/Supabase, so **pgvector** is used.
- Jev thresholds: **AI-labelled ~300 creators, user spot-checks 20%**.
- Live keys (`TYPESAFE_API_KEY`, `YOUTUBE_API_KEY`, `GROQ_API_KEY`/`GOOGLE_API_KEY`) will be added to the environment; until then, build and test against recorded samples.

**Build order (one PR each):** `shared-core` (F1.1, F1.2, F1.5, F1.6) → `creator-db` (F1.3, F1.4) → `youtube-adapter` (F1.9) → `run-engine` (F0.6, F1.7, F1.8, F1.10) → `results-ui` (F1.12) → F1.11 → F1.13.

| ID | Feature | Status | Spec | Main files |
|---|---|---|---|---|
| F1.1 | `CreatorProfile` + `Post` types | done (`shared-core`) | §4.1 | `app/platforms/base.py` |
| F1.2 | Platform adapter interface | done (`shared-core`) | §4.2 | `app/platforms/base.py` |
| F1.3 | Creator DB: `creators`, `creator_snapshots`, `creator_judgments`, `creator_persons`, `person_links` + pgvector | done (`creator-db`) | §4.4, §4.9 | `app/models/creator.py`, migration `d7a2e5c9b1f3` (pgvector + HNSW), `app/creators/repository.py`, `tests/creators/` |
| F1.4 | Caches: profile (7 d), search results (24–72 h), embeddings + Jev answers by content hash | done (`creator-db`) | §4.4, §4.11 | profile reuse (`split_fresh`, 7 d), Jev answer + embedding caches by content hash (`app/creators/repository.py`); search cache already in `app/discovery/cache.py` |
| F1.5 | Metrics: robust stats, momentum, outperformance, per-platform percentiles, IsolationForest anomaly | done (`shared-core`) | §4.5 | `app/metrics/` (stats, baselines, anomaly, pricing, compute, constants), `tests/shared_core/test_metrics.py` |
| F1.6 | Jev judging questions + scoring combine | done (`shared-core`) | §4.6–4.7 | `app/judge/questions.py`, `constants.py`, `combine.py`, `tests/shared_core/test_judging.py` |
| F1.7 | Generic discovery graph (strategy → sourcing → filter → fetch → metrics → top-up round if too few pass → shortlist → judge → score → reasons) | done (`run-engine`) | §4.3, §4.14 | `app/discovery/graph.py`, `nodes.py`, `state.py`, `brief.py`, `prompts.py`, `legacy.py`, `app/llm/embeddings.py`, `tests/discovery/test_graph.py` |
| F1.8 | Platform selection (preset + Jev check) and probe-then-expand. User toggle moves to F1.12 | done (`run-engine`) | §4.9 | `app/discovery/nodes.py` (`platform_select`, `fan_out`, `probe_check`) |
| F1.9 | YouTube adapter on the core (+ recent-video trend search, quota discipline) | done (`youtube-adapter`) | §4.8 | `app/platforms/youtube.py`, `youtube_api.py`, `tests/platforms/`, recorded fixture `tests/fixtures/youtube/recording.json` (re-record: `python -m scripts.record_youtube_fixtures`) |
| F1.10 | Streaming results per branch (Inngest Realtime `leads` topic, backend side). The UI doesn't read the topic yet: F1.12 | done (`run-engine`) | §4.12 | `app/discovery/runtime.py` |
| F1.11 | YouTube 30-day data refresh/delete job: refresh useful creators (scored, in results or saved; old-engine results too), delete the rest after 30 days, purge old snapshots and run metrics, update or expire old results (`data_expired` shown in the UI) | done (`youtube-refresh`) | §4.4 | `app/creators/refresh.py`, `app/creators/constants.py`, `app/inngest/functions.py` (`refresh_youtube_data`, daily 09:17 UTC), `app/discovery/legacy.py` (`data_as_of`), `tests/creators/test_refresh.py`, frontend `CreatorBadges.tsx`, `InfluencerRow.tsx` |
| F1.12 | Frontend results: badges (rising, on trend, check engagement, country unknown), live "scored so far" count from the `leads` topic, brief-form fixes (K12), progress banner and Retry fixes. Score breakdown (fit, health) was already shown | done (`results-ui`) | §4.13 | `components/CreatorBadges.tsx`, `app/ListOfInfluencer/InfluencerRow.tsx`, `InfluencerDetailSheet.tsx`, `components/CampaignProgressBanner.tsx`, `inngest/channels.ts`, `app/actions/realtime.ts`, `lib/countries.ts`, `lib/creatorSize.ts`, `app/campaign/[id]/details/SubmitCampaignButton.tsx`, `store/campaignStore.ts` |
| F1.12b | Platform choice in the brief: `campaign.platforms` (empty = automatic preset + Jev check); a choice skips the Jev check and probes; unbuilt platforms warn. Form shows YouTube + Instagram/X/LinkedIn as coming soon (`platform-choice`) | done | §4.9, §4.13 | `app/discovery/brief.py`, `app/discovery/nodes.py` (`platform_select`), `frontend/components/MultiPlatform.tsx`, `SubmitCampaignButton.tsx`, `store/campaignStore.ts` |
| F1.12c | Credit estimate before a run (needs billing, Phase 2) | later | §4.13, §5 | — |
| F1.13 | Switch to the new pipeline: production migrated (Nov 4), old pipeline (`app/my_agent/`, `scripts/run_local.py`, `app/core/get_youtube_client.py`), its runner and the `DISCOVERY_ENGINE` switch removed; `google-api-python-client` and `apify-client` dropped from requirements. Needs `TYPESAFE_API_KEY` and `GROQ_API_KEY` in Vercel before merge | done (`engine-switch`) | §0, §4.14 | `app/inngest/functions.py`, `app/workflow/runtime.py`, `app/core/config.py`, `requirements.txt` |
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
| K1 | Eval test fixture had no "collaboration" wording and exposed package terms; fixed the fixture and added edge-case tests (`foundations`) | done |
| K2 | Outreach (`generate_creator_pitch`, `repair_creator_pitch`) and the eval judge now call `app/llm` (routes `pitch`, `judge_eval`) with cost logging per outreach job; `app/core/model.py` removed. Same model as before (gemini-3.5-flash-lite) until K3 picks one (`outreach-llm`) | done |
| K6 | Tune Jev questions and thresholds on ~300 AI-labelled creators (user spot-checks 20%). First live check (3 real creators, Nov 3): `safety_risk` 1.43 for purely technical LLM videos (Ayush Singh) is a misread: reword the safety question with concrete examples; `posts_on_trend` ~0.6 for all three: raise `TREND_THRESHOLD` or tighten the question | next |
| K7 | `outreach_pitches` index name differed between migration and model; aligned in migration `8e6c2e1ac3e7` (`perf`). `alembic check` is now clean | done |
| K8 | Production database migrated to head (`e4b8c1d6a2f9`) on Nov 4 through the Neon connector. Vercel deploys don't run migrations: apply each new migration the same way | done |
| K9 | Saved demo data has a wrong channel ID: `UCkw4JCwteGrDHIsyIIKo4tQ` is labelled "Krish Naik" but belongs to edureka!. Only names/numbers are shown, so nothing breaks; fix when regenerating demo data | later |
| K10 | Jev key was an OpenRouter key, so TypeSafe's server rejected it. Fixed: the client detects OpenRouter keys and uses OpenRouter's Jev gateway, pinned to `typesafe/jev-1.14-20261014` (`jev-openrouter`) | done |
| K11 | YouTube's API doesn't include a channel's "links" section, so cross-platform links are rarely found from YouTube alone (0 of 8 in the first recording). Links will mostly come from X/Instagram profiles and link pages | later |
| K12 | Brief form: country read from the first 2 letters of its name ("United States" → `UN`, "Germany" → `GE` = Georgia), empty fields silently filled with the DataLaunch sample, languages always en+hi, hard-coded website, location/size not restored on reload. Fixed: ISO codes read from the picker's flag emoji, required fields, languages from the country (`results-ui`) | done |
| K13 | Old vs new comparison (Nov 4, 3 briefs, blind-rated 1-5): fitness/India new 3.4 vs old 3.2 (both fine); invoicing/US new 2.4 vs old 2.5; API monitoring/UK-US new 1 lead vs old 6 (2.8). The new engine never breaks size/country rules; the old one ignores the max-subscriber limit (5 of 24 top results too big). New engine's weakness is recall on niche B2B: long sentence-like search phrases return 0-17 channels, and channel search favours tiny channels named after the keyword. Fix on `discovery-recall`: short 2-5 word searches, fewer trend searches, relevance order for the top-up. Also (no extra quota): fused ranking of candidates across searches, and the cheap subscriber check for every candidate, not just the first 150. Offline pass rates (1,246 candidates): channel search 5-8%, trend 0-13%, video 6-25% (small sample). Re-test live with K20 | in progress |
| K14 | No result reached "Strong Buy" (top 67). Cause: Jev answers are probability-weighted averages, which pull fit toward the middle, and the safety question also flags health/clickbait claims, so the average risk penalty is about 9 points. Fixed offline: labels recalibrated to 60/45 on 63 scored creators + 19 blind ratings (`discovery-recall`). Left for K6: split "misleading claims" from "controversy" in the safety question and re-ask Jev | done |
| K15 | Neon branches renamed (Nov 4): the live branch is now `production` (default, endpoint `ep-calm-sky`). The old root branch can't be deleted (Neon never deletes a project's root branch), so it's renamed `old-production-unused`; its data (April) is all in `production` | done |
| K16 | YouTube sends `rateLimitExceeded` (not `quotaExceeded`) once the daily search allowance is used up; the adapter kept trying every search and the run finished with 0 leads and one warning per search. Fixed: treated as out of quota, one clear warning. YouTube's day resets at midnight Pacific time (`discovery-recall`) | done |
| K17 | Creators with no country on YouTube, when the brief sets target countries: kept, score × 0.8 (`COUNTRY_UNKNOWN_FACTOR`), flagged `country_unknown` (decided Nov 4, `discovery-recall`). The results screen should show the flag as a badge (F1.12) | done |
| K18 | Deletion requests (GDPR/DPDP): a creator or user asks for their data to be deleted; the refresh job should process a queue of requests (`repo.delete_creator` exists). Not built | next |
| K19 | LangGraph checkpoint threads untouched for 30 days (old pipeline, discovery and outreach) are deleted by the nightly refresh job via the saver's `adelete_thread`; they only matter for resuming a run in progress (`checkpoint-cleanup`) | done |
| K20 | Re-record the YouTube test fixture (`python -m scripts.record_youtube_fixtures`, ~210 quota units) so it holds the channels fused ranking picks; tests currently use all 100 recorded search results as candidates | later |
| K21 | Page load speed (Nov 4, `perf`). Measured: production cold start 7.7 s vs ~0.3 s warm; campaign list 162 ms p50 / 2.75 s p95 at 10 concurrent (loaded every campaign's results JSON to count leads, full table scan); `/status` opened a new DB connection per call; saved leads full table scan. Fixed: leads counted in Postgres, indexes `campaigns(user_id, created_at)` and `saved_leads(campaign_id)`, no per-call connection, results JSON passed through as text, LangGraph loaded only when a run starts (cold import 1.48 → 0.86 s), Fluid compute on, keep-warm Inngest cron every 5 min. Benchmark: scratch `bench/` (simulated 2 ms DB delay) | done |
| K22 | Re-measure production cold start after the `perf` deploy, and consider trimming the Python bundle (exclude `tests/`, fixtures) if cold starts stay above ~2 s | next |
| K23 | Inngest rejected every app sync since the run-engine change: `run_campaign` asked for 10 concurrent runs, the free plan allows 5. So the nightly refresh and keep-warm functions were never registered and run settings were stale. Fixed: account limit 5 (`INNGEST_PLAN_MAX_CONCURRENCY`), test guards every function; re-sync after deploy (`inngest-limits`) | done |
| K3 | Route models for `strategy`, `pitch`, `reply` are placeholders (current Gemini first); pick them with the LangSmith evals | next |

## Open questions waiting on the user
- `TYPESAFE_API_KEY` must be added in the environment settings before testing Jev live.
- Vendor prices in the spec come from third-party sources; confirm before launch.

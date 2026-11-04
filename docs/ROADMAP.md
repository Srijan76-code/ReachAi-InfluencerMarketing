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

## Look and feel
| ID | Feature | Status | Main files |
|---|---|---|---|
| U1 | One UI everywhere (`ui-system`): written guide (look, type scale, controls, words), shared controls (`Select` instead of browser dropdowns, `Field`/`Input`/`NumberInput`/`TextArea`, `StatStrip`/`StatTile`, `SectionHeader`, `btn`/`btnPrimary`); Deals board, card, panel and dialogs restyled to match the creator panel; reply helper shown as its own section with a hint when no quote is entered; post tiles use `StatTile` | done | `docs/UI_GUIDE.md`, `frontend/lib/ui.ts`, `frontend/components/ui/{field,select,stat}.tsx`, `frontend/components/deals/*`, `frontend/components/PostTabs.tsx` |
| U2 | Move the remaining hand-styled controls (brief form, outreach page, share dialog) onto the shared pieces | later | `frontend/app/campaign/[id]/details/`, `frontend/app/campaign/[id]/outreach/` |

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
| F1.15 | Lead v2 data (PR 1 of the creator panel): per-post cards (thumbnail, format, reach, × usual, brief topics matched, sponsored), post signals (fit posts, sponsored posts, sponsor brands, median reach), score parts that add up to the score, trend, verified, person id, brief topics kept for the nightly refresh; `GET /api/campaigns/{id}/skipped` (how many looked at, why the rest were left out, in plain buckets). All computed in code from data already fetched: no extra API, Jev or LLM calls (`lead-v2`) | done | §4.13, §10 | `app/metrics/posts.py`, `app/metrics/constants.py`, `app/discovery/legacy.py`, `app/discovery/skipped.py`, `app/judge/combine.py` (`parts`), `app/platforms/base.py`, `app/platforms/youtube.py`, `app/creators/refresh.py`, `app/api/routes/campaign.py`, `frontend/data/influencerList.tsx`, `tests/discovery/test_lead_v2.py` |
| F1.16 | Results list (PR 2): loading skeletons; sorts (best value, views, engagement) and filters (rising, on trend, hide unusual engagement, saved only) with an active count and reset; name/niche search; view remembered per campaign (localStorage); platform chips (shown once results span 2+ platforms); save failures shown, double clicks ignored; keyboard shortcuts (j/k, Enter, s, x, /, Esc, ?; j/k step through open panels); "looked at N, M left out" note from `/skipped` (`results-list`) | done | §4.13 | `app/ListOfInfluencer/InfluencerPage.tsx`, `lib/leadView.ts`, `components/LeadListSkeleton.tsx`, `components/SkippedNote.tsx`, `store/campaignStore.ts`, `content/docs/understanding-results.mdx` |
| F1.16b | Frontend unit tests: the repo has no JS test runner; `lib/leadView.ts` is pure and was checked in a browser run only. Add Vitest and cover filter/sort/parse | later | — | `frontend/lib/leadView.ts` |
| F1.17 | Creator panel (PR 3): "why this score" bars from `score_parts` (incl. the country-unknown factor), data freshness, views trend, verified tick, post tabs (Best match / Above their usual / Latest) with thumbnails, matched topics, sponsored tags, × usual and age; summary line from `signals`; older results keep the old list. Backend: posts under 7 days are "new" (no × usual, left out of the median); topics matched on title + the description's opening paragraph only (link lists caused false matches in the recording) (`creator-panel`) | done | §4.13 | `InfluencerDetailSheet.tsx`, `components/ScoreParts.tsx`, `components/PostTabs.tsx`, `lib/posts.ts`, `backend/app/metrics/posts.py`, `backend/app/metrics/constants.py` |
| F1.17b | Platform switcher in the creator panel: one person's YouTube / Instagram / X / LinkedIn side by side via `person_id`. Needs a second platform's adapter (X first) | later | §4.13, §6 | `InfluencerDetailSheet.tsx` |
| F1.20 | Campaigns page: names from the brief ("DataLaunch · Sales · India", set on run unless the user named it; older placeholder names shown the same way), rename (`PATCH /api/campaigns/{id}`) and delete (`DELETE`, cascades to saved leads and outreach; refused while a search runs), cards show creators found, real status (Ready / Searching / No creators / Failed / Draft) and "updated 2 days ago"; drafts never run hidden after a day. Production cleanup Nov 4: 7 empty campaigns deleted (backup branch `backup-before-campaign-cleanup-2026-11-04`) (`campaign-names`) | done | §4.13 | `backend/app/api/campaign_names.py`, `backend/app/api/routes/campaign.py`, `frontend/app/campaign/page.tsx`, `frontend/app/campaign/_components/CampaignCard.tsx`, `frontend/types/campaign.ts` |
| F1.18 | Compare tray and share links (PR 4a): compare 2-4 creators (in the app and on shared pages); Drive-style sharing: personal links per email (no sign-in, no account, no emails sent by us) and an "anyone with the link" link (30 days); view only; all creators or a selection; fair prices off by default, per link; revoke; view count and last opened; allowlist so contacts and private fields never leave; `noindex`, `no-store`, `no-referrer`. Migration `a1d4f7c2e9b3` (`share-links`) | done | §4.13, §10 | `backend/app/models/share_link.py`, `backend/app/sharing/view.py`, `backend/app/api/routes/share.py`, `frontend/components/ShareDialog.tsx`, `frontend/components/CompareTray.tsx`, `frontend/app/s/[token]/`, `InfluencerRow.tsx`, `InfluencerDetailSheet.tsx` (read-only) |
| F1.21 | Results page polish (`results-polish`): campaign tabs Brief · Creators · Outreach (max 5; Deals and Results added when built; cross-campaign items in the main navbar, incl. New campaign); toolbar (search icon, Filter, Sort, Share, Start outreach, ⋯ with Export and shortcuts); "checked · kept" chip with reasons popover; Shortlist switch replacing the unreachable Saved page (old URL redirects); rows: truncating names, all badges (icons at 3+), one-line labels, whole-number Impact with label-matched ring colours; panel order fit → posts → metrics → why this score; "View on {platform}"; photo lightbox; subtle highlight cleared on close | done | §4.13 | `InfluencerPage.tsx`, `InfluencerRow.tsx`, `InfluencerDetailSheet.tsx`, `CreatorBadges.tsx`, `SkippedNote.tsx`, `ExportDialog.tsx`, `Header.tsx`, `CampaignTabs.tsx`, `lib/useCreateCampaign.ts` |
| F1.18b | Sharing PR 4b (`share-reviewers`, simplified in `share-simple`): Reviewer role on personal links (👍/👎 + comment per creator, no account; owner sees a chip per row and a Feedback section; kept after access is removed; public links stay view-only). Email-code contact sharing was built, then removed the same day (decided: links never share contacts); migration `c4f8e1a2b6d9` drops its storage. Share dialog redone Drive-style (invite + Can view/Can review, copy, ⋯ for prices/remove, Restricted/Anyone) | done | §4.13, §10 | `backend/app/api/routes/share.py`, `backend/app/sharing/view.py`, `frontend/components/ShareDialog.tsx`, `frontend/components/Feedback.tsx`, `app/s/[token]/SharedShortlist.tsx` |
| F1.22 | Feel (`motion-share-scope`): press feedback on every button/tab/menu item (scale 0.97 via Web Animations, Android vibration 8 ms; Mac trackpad and iPhone haptics aren't available to websites), sliding `Segmented` switch (All/Shortlist, post tabs, share scope), sliding campaign-tab underline, tab content fade-in (`template.tsx`), tab loading placeholder; all off under prefers-reduced-motion. Share scope follows the view (Shortlist when viewing it) | done | §4.13 | `components/Feel.tsx`, `components/ui/segmented.tsx`, `app/campaign/[id]/template.tsx`, `loading.tsx`, `CampaignTabs.tsx`, `ShareDialog.tsx` |
| F1.18e | Sharing command centre (`share-center`): Share opens a side panel with People (access), Activity (opens deduped per 30 min + every reaction, newest first, from `share_events`, migration `f7c3d8e2a4b6`) and By creator (👍/👎 + comments, bulk Shortlist approved / Add approved to deals); unseen-activity dot on Share (localStorage marker); list filters Approved by reviewers / Has feedback. `GET /api/campaigns/{id}/share-activity`. No email needed: links are copied and sent by the founder | done | §4.13, §10 | `backend/app/api/routes/share.py`, `backend/app/models/share_link.py`, `frontend/components/SharingPanel.tsx`, `frontend/components/ShareManager.tsx`, `lib/leadView.ts` |
| F1.18c | Teams: invite teammates as editors (save, outreach, shared credits). Not a share-link role | later | §5 | — |
| F1.19 | Competitor promoted (PR 5): which creators already promote a competitor, from sponsor brands. After the X adapter | later | §4.13, §6 | — |

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
**Agent plan (decided Nov 4):** the agent proposes, the founder approves everything. Build order: F6.8 "Needs you" queue → F6.5 Connect Gmail → F7.3 live posts → F7.4 + F7.5 Results v1 (links, codes, views) → F7.4 signups and sales.

| ID | Feature | Status | Spec |
|---|---|---|---|
| F6.1 | Identity: email ranking, sponsor blocklist, Jev pick, verification, first name, contact ledger, suppression list | later | §7.1 |
| F6.2 | Creator dossier | later | §7.2 |
| F6.3 | Primary channel per creator | later | §7.3 |
| F6.4 | Pitch quality: founder voice, soft vs offer A/B, plain-text first email | later | §7.4 |
| F6.5 | Connect Gmail (`gmail-inbox`): Google OAuth (send + readonly, offline), refresh token encrypted with Fernet (key `TOKEN_ENCRYPTION_KEY`, else derived from the client secret), signed 10-minute state; `connected_accounts` + deal email fields (migration `b5c1e8f3a9d4`); approving a message sends it in the deal's thread (In-Reply-To), daily cap 40; first pitch sent from Outreach starts the deal; replies pulled from threads ReachAI started (on opening Deals, at most every 2 min per thread, and an Inngest cron every 30 min), quoted history stripped, read once by Jev with the negotiation context; disconnect revokes at Google; `/privacy` and `/terms` (Limited Use statement) for Google's Branding page. Consent screen still in Testing until Branding is filled in | done | §7.5 | `backend/app/gmail/`, `backend/app/api/routes/gmail.py`, `backend/app/inngest/functions.py`, `frontend/components/GmailConnect.tsx`, `frontend/app/privacy`, `frontend/app/terms`, `tests/gmail/` |
| F6.5b | Outlook (Microsoft Graph); bounce detection; Google verification + CASA once there are outside users | later | §7.5 | — |
| F1.23 | Add a creator by channel link (`gmail-inbox`): YouTube channel id or @handle → measured like a search (metrics, fair price, posts; ~3 quota units, no Jev or LLM), added to the campaign as "Added by you" and to Deals | done | §4.13 | `backend/app/creators/by_link.py`, `backend/app/api/routes/deals.py`, `frontend/components/deals/AddCreatorsDialog.tsx` |
| F6.6 | Claim check | later | §7.6 |
| F6.7 | Follow-up sequences (Inngest) | later | §7.7 |
| F6.8 | "Needs you" queue (`needs-you`), deals part: `agent_proposals` (migration `a3b9d5e1c7f2`); code suggests one next step per deal (follow-up ×2, record quote from a pasted reply, counter / accept with a ready message, agree when they accept our offer, mark lost, chase a late post ×3, move to Live, mark paid), with the reason; Approve (messages: copy and mark sent) / Edit / Reword with AI / Skip, all logged on the timeline; skipped ones never return; pasted reply read by Jev (new `declined`, `agrees`, `gives_price` questions, `reply-v2`); greeting uses a first name only when the channel name looks like a person's. Outreach first messages join the queue with Gmail (F6.5) | done | §7.8 | `backend/app/agent/`, `backend/app/deals/changes.py`, `backend/app/api/routes/deals.py`, `frontend/components/deals/NeedsYou.tsx`, `DealPanel.tsx`, `tests/agent/` |
| F6.8c | Deals rework (`deals-memory`): negotiation memory (counters move from our last offer toward their ask, never below it or above fair; final offer after 3 rounds; mark lost if still too high), Jev reads replies with the negotiation so far (`reply-v3`), AI may not mention the full counter in a fee + commission message (bug: "the $65 we discussed"), quote edits within 2 min merge into one timeline entry, prices under $50 round to the dollar; Board \| To do switch with bulk select / approve / skip (edits kept); dot on cards with a to-do; panel shows what matters at each stage (next step + reply box, quote with Save and loading, offers so far, agreed price and date, post and payment), terms folded into one line, notes and history folded; app-wide sentence-case labels and ⓘ tooltips | done | §7.8, §8.7 | `backend/app/deals/negotiation.py`, `backend/app/agent/proposals.py`, `backend/app/api/routes/deals.py`, `frontend/components/deals/*`, `frontend/components/ui/stat.tsx`, `docs/UI_GUIDE.md` |
| F6.8d | Per-step automation setting per campaign (follow-ups and late-post nudges automatic; money and terms always approved). Needs Gmail sending (F6.5) | next | §0, §7.5 | `backend/app/agent/`, Deals settings |
| F6.8b | Needs-you count on the Deals tab and in the navbar (across campaigns); a cron so time-based suggestions (follow-ups, late posts) can notify without opening the page | later | §7.8 | `CampaignTabs.tsx`, `app/inngest/functions.py` |
| F6.1b | Creator first name for greetings (Jev picks it from the channel's about text; today a cautious code rule) | later | §7.1 | `app/deals/negotiation.py` (`greeting_name`) |
| F6.9 | Inbox + reply classification | later | §7.9 |
| F6.10 | Assisted DMs | later | §7.10 |
| F6.11 | Reply-rate analytics | later | §7.11 |

## Phase 7: Deals, tracking, payments · §8
| ID | Feature | Status | Spec |
|---|---|---|---|
| F7.1 | Deals v1 (`deals`): `creator_deals` + `deal_events` (migration `e5a9c2d7f3b1`); Deals tab (4th) with a board Contacted → Negotiating → Agreed → Content → Live → Paid (+ Lost, hidden), drag-and-drop and ⋯ menu; deal panel with terms (deliverable, post-by, deal type + commission, usage rights, exclusivity, #ad), live post link (checked against the platform), mark paid, notes, timeline; summary strip (deals, committed vs budget, live x/y, paid); Add to deals from panel / selection / shortlist picker. Auto stage moves from outreach events come with F6 | done | §8.1, §8.5 | `backend/app/models/deal.py`, `backend/app/api/routes/deals.py`, `frontend/components/deals/*`, `app/campaign/[id]/deals/` |
| F7.2 | Brief, contract, creator portal, draft review | later | §8.2 |
| F7.3 | Live detection + post checklist + alerts (step 4 of the agent plan) | next | §8.3 |
| F7.4 | Snapshots, own short links, promo codes (v1, step 5); signups and sales by snippet or server event (step 6) | next | §8.4 |
| F7.5 | Results tab: views on days 1–60, clicks, codes, cost per view and per click vs forecast, rebook. Self-test with the founder's own channel and a second email (step 5) | next | §8.5 |
| F7.6 | Pay-on-proof requests, mark paid, reminders, tax-ID collection | later | §8.6 |
| F7.7 | Negotiation helper done (`deals`): fair range for the exact deal (format ×, usage +, exclusivity +; constants in `app/deals/constants.py`, starting values from market guides), verdict great/accept/counter/walk-away, deal type from the goal, reply message: code template + Jev reads the pasted creator reply (`creator_reply_questions`, angle budget/performance/scope) + optional LLM rewording (route `counter`: Groq gpt-oss-120b → Gemini Flash-Lite) checked to keep exactly our numbers. Left: budget planner (knapsack), tune multipliers with agreed prices | in progress | §8.7 | `backend/app/deals/negotiation.py`, `backend/app/deals/reply.py` |
| F7.9 | Negotiation agent (`negotiation-agent`): LangGraph judge → guard → write → check; Jev reads their ask from the amounts in their words and decides move, deal type, commission step and concession; code turns it into amounts within the ceiling (fair top +15%, budget left, never below our last offer); LLM (route `reply`) writes with the creator's words, checked by code (only the decided amounts) and Jev (no extra promises), one rewrite then a standard fallback; runs on Gmail replies and pasted or typed ones; replaces the Nov 4 formula and templates (`app/deals/reply.py`, `thread.py`, the `/counter` endpoint removed); `quoted_commission_pct` (migration `c7d2a4f9e1b8`); Deals summary as one line | done | §8.6b | `backend/app/negotiation/`, `backend/app/judge/questions.py`, `backend/app/judge/constants.py`, `frontend/components/deals/DealPanel.tsx`, `DealsBoard.tsx`, `tests/negotiation/` |
| F7.9b | Negotiation evals: a LangSmith set of real creator replies with the move a good negotiator would make; tune `CONCESSION_SHARE`, ceiling and Jev wording on it | next | §8.6b | `backend/tests/evals/` |
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
| K9 | Demo data: `UCkw4JCwteGrDHIsyIIKo4tQ` is labelled "Krish Naik" but belongs to edureka!. Since creator names now link to their channel, the demo links this one to a YouTube search instead; fix the id when regenerating demo data | later |
| K10 | Jev key was an OpenRouter key, so TypeSafe's server rejected it. Fixed: the client detects OpenRouter keys and uses OpenRouter's Jev gateway, pinned to `typesafe/jev-1.14-20261014` (`jev-openrouter`) | done |
| K11 | YouTube's API doesn't include a channel's "links" section, so cross-platform links are rarely found from YouTube alone (0 of 8 in the first recording). Links will mostly come from X/Instagram profiles and link pages | later |
| K12 | Brief form: country read from the first 2 letters of its name ("United States" → `UN`, "Germany" → `GE` = Georgia), empty fields silently filled with the DataLaunch sample, languages always en+hi, hard-coded website, location/size not restored on reload. Fixed: ISO codes read from the picker's flag emoji, required fields, languages from the country (`results-ui`) | done |
| K13 | Old vs new comparison (Nov 4, 3 briefs, blind-rated 1-5): fitness/India new 3.4 vs old 3.2 (both fine); invoicing/US new 2.4 vs old 2.5; API monitoring/UK-US new 1 lead vs old 6 (2.8). The new engine never breaks size/country rules; the old one ignores the max-subscriber limit (5 of 24 top results too big). New engine's weakness is recall on niche B2B: long sentence-like search phrases return 0-17 channels, and channel search favours tiny channels named after the keyword. Fix on `discovery-recall`: short 2-5 word searches, fewer trend searches, relevance order for the top-up. Also (no extra quota): fused ranking of candidates across searches, and the cheap subscriber check for every candidate, not just the first 150. Offline pass rates (1,246 candidates): channel search 5-8%, trend 0-13%, video 6-25% (small sample). Re-test live with K20 | in progress |
| K14 | No result reached "Strong Buy" (top 67). Cause: Jev answers are probability-weighted averages, which pull fit toward the middle, and the safety question also flags health/clickbait claims, so the average risk penalty is about 9 points. Fixed offline: labels recalibrated to 60/45 on 63 scored creators + 19 blind ratings (`discovery-recall`). Left for K6: split "misleading claims" from "controversy" in the safety question and re-ask Jev | done |
| K15 | Neon branches renamed (Nov 4): the live branch is now `production` (default, endpoint `ep-calm-sky`). The old root branch can't be deleted (Neon never deletes a project's root branch), so it's renamed `old-production-unused`; its data (April) is all in `production` | done |
| K16 | YouTube sends `rateLimitExceeded` (not `quotaExceeded`) once the daily search allowance is used up; the adapter kept trying every search and the run finished with 0 leads and one warning per search. Fixed: treated as out of quota, one clear warning. YouTube's day resets at midnight Pacific time (`discovery-recall`) | done |
| K17 | Creators with no country on YouTube, when the brief sets target countries: kept, score × 0.8 (`COUNTRY_UNKNOWN_FACTOR`), flagged `country_unknown` (decided Nov 4, `discovery-recall`). Revised Nov 4 (`jev-country`): Jev now judges the audience's country in the same request; confident target-country answers get no penalty and show "judged from their posts", confident "other" answers are dropped, and only real unknowns keep × 0.8. Measure how often each happens on the next live run (`run_candidates.flags`) | done |
| K24 | The fair price (valuation) is computed before Jev runs, so a Jev-judged country doesn't adjust it yet (the cost-per-1k-views does). Recompute valuation after judging if the country factor matters | later |
| K18 | Deletion requests (GDPR/DPDP): a creator or user asks for their data to be deleted; the refresh job should process a queue of requests (`repo.delete_creator` exists). Not built | next |
| K19 | LangGraph checkpoint threads untouched for 30 days (old pipeline, discovery and outreach) are deleted by the nightly refresh job via the saver's `adelete_thread`; they only matter for resuming a run in progress (`checkpoint-cleanup`) | done |
| K20 | Re-record the YouTube test fixture (`python -m scripts.record_youtube_fixtures`, ~210 quota units) so it holds the channels fused ranking picks; tests currently use all 100 recorded search results as candidates | later |
| K21 | Page load speed (Nov 4, `perf`). Measured: production cold start 7.7 s vs ~0.3 s warm; campaign list 162 ms p50 / 2.75 s p95 at 10 concurrent (loaded every campaign's results JSON to count leads, full table scan); `/status` opened a new DB connection per call; saved leads full table scan. Fixed: leads counted in Postgres, indexes `campaigns(user_id, created_at)` and `saved_leads(campaign_id)`, no per-call connection, results JSON passed through as text, LangGraph loaded only when a run starts (cold import 1.48 → 0.86 s), Fluid compute on, keep-warm Inngest cron every 5 min. Benchmark: `backend/scripts/bench/` (seed + run, simulated 2 ms DB delay); raw results in `docs/benchmarks/2026-11-04-read-endpoints/`; summary in README | done |
| K22 | Re-measure production cold start after the `perf` deploy, and consider trimming the Python bundle (exclude `tests/`, fixtures) if cold starts stay above ~2 s | next |
| K23 | Inngest rejected every app sync since the run-engine change: `run_campaign` asked for 10 concurrent runs, the free plan allows 5. So the nightly refresh and keep-warm functions were never registered and run settings were stale. Fixed: account limit 5 (`INNGEST_PLAN_MAX_CONCURRENCY`), test guards every function; re-sync after deploy (`inngest-limits`) | done |
| K3 | Route models for `strategy`, `pitch`, `reply` are placeholders (current Gemini first); pick them with the LangSmith evals | next |

## Open questions waiting on the user
- `TYPESAFE_API_KEY` must be added in the environment settings before testing Jev live.
- Vendor prices in the spec come from third-party sources; confirm before launch.

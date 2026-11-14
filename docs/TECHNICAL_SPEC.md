# ReachAI — Technical Spec: Multi-Platform Discovery, Outreach Loop, Billing

> Status: **plan for review. No code has been changed yet.**
> Date: 2026-11-03
> Scope: everything needed to go from "YouTube discovery + pitch generation + CSV export" to an end-to-end creator marketing product for startup and solo founders.

---

## 0. Decisions this spec is built on

| Area | Decision |
|---|---|
| Customer (ICP) | Startup / solo founders, both B2B/technical and consumer products |
| Market | Global, tested as we go |
| Positioning | **Quality + fair price**: "the creators who will actually convert for you, and what you should pay them" |
| Platforms (build order) | Shared core → **X** → **Instagram** → **LinkedIn**. YouTube stays and moves onto the shared core |
| Data sources | YouTube Data API · X through a third-party provider, with the official API behind a switch · Instagram through Apify (HikerAPI later if cost or speed needs it) · LinkedIn through **public, logged-out post search only** |
| Judgment layer | **Jev (TypeSafe AI)** for every yes/no, label and scale judgment |
| Numbers | **Code, statistics and ML**: metrics, anomaly detection, scoring, valuation. No LLM involved |
| Negotiation | **An agent: Jev reads and decides, code guards, the LLM writes (decided Nov 5).** Jev picks the move, deal type, commission step (0–25%) and how far to concede from options code gives it; code turns those into exact amounts within the ceiling (fair top +15%, never over the budget left, never below our last offer) and never lets a model state a price. The writer sees the creator's own words (screened by Jev for injection) and every amount is checked. Default aim: good value while keeping the creator happy. Replaces the code formula and templates (§8.7) |
| Text generation | LLM through the **LangSmith LLM Gateway**, behind our own thin wrapper |
| Pricing | **Only creator searches cost credits** (YouTube 1, X 3, Instagram 4, LinkedIn 8); outreach, negotiation, tracking and agent use are unlimited. Free (3/mo) · Solo $12 / ₹499 (25) · Pro $29 / ₹1,299 (80) · packs that never expire. Welcome credits, refund guarantee, INR prices, referrals (decided Nov 12, §5) |
| Payments | **Dodo Payments as merchant of record** (handles global tax, UPI, INR). Billing logic lives in our backend; Dodo only collects money. Replaces Cashfree (Nov 12, §5.4) |
| Validation | Skipped. To compensate, every user action is instrumented from day one (§11) |
| Platform choice | **Preset by founder type + AI check + user toggle.** B2B/AI → X, LinkedIn, YouTube · Consumer → Instagram, YouTube (§4.9) |
| Discovery strategy | **Cheapest-first ladder**: our creator DB → YouTube → expand through creators' own links → small native search only to fill gaps (§4.9) |
| Extra sources | Competitor sponsors, lookalikes, founder's own X followers, pre-warmed trending niches (§4.10) |
| Results UX | **Stream results as they arrive** (§4.12) |
| Discovery quality rule | **Probe every selected platform, expand where a probe beats the current top N**; fit floor as a safety net; recall benchmark ≥ 90% (§4.9) |
| Cross-platform scores | **A score means the same on every platform (decided Nov 13).** Each creator is ranked against creators on the same platform and size: engagement benchmarks per platform from our own measured creators (real peers replace them at 200 per platform/tier), reliability bands 1.3× wider for Instagram reels, the country cut only where the platform lists a country, and the same Strong Buy / Consider / Avoid lines everywhere. Published benchmarks were too inconsistent to use (different denominators per source) |
| Creator country when the platform lists none | **Jev decides, no estimating in code (decided Nov 4).** For creators with no listed country, the per-creator Jev request gets one more question: which of the brief's countries is the audience mostly in (`other` / `not_stated` allowed), from bio, titles and description openings. Code only applies thresholds: a target country at ≥ 0.6 confidence counts as that country (no penalty, marked "judged from their posts"); `other` at ≥ 0.75 drops the creator; anything else keeps them flagged `country_unknown`, × 0.8 only on platforms that normally list a country (YouTube, LinkedIn); on Instagram and X a missing country says nothing, so no cut (changed Nov 13). No extra requests. Web search was rejected (paid vendor, slow, finds where the creator lives, not the audience) |
| Sharing | **Drive-style, no viewer accounts (decided Nov 4, revised the same day).** Invite by email (personal link, Can view or Can review) or "anyone with the link" (view only, 30 days). Fair prices per link, off by default. **Contact details are never shared through links**, so there are no email codes and ReachAI sends no email. Editors are a Teams feature, not a link role |
| Pipeline rollout | **The new discovery graph replaces the old pipeline (decided Nov 4).** The 3-brief comparison showed it never breaks size/country rules and leads on the consumer brief; its recall on niche B2B is tuned on top. The old pipeline and the `DISCOVERY_ENGINE` switch are removed (roadmap F1.13) |
| Run execution | LangGraph runs and resumes the pipeline from Postgres checkpoints; Inngest starts, retries (resume), limits (2 per user, 5 total: Inngest free-plan maximum, was 10) and cancels runs (a re-run cancels the previous one); platforms are parallel LangGraph branches; Vercel; Postgres caches (§4.14) |
| After the deal | Founder pays creators directly (we send pay-on-proof requests and track); own short links; promo codes + signup snippet/server event; tracking included in paid plans (§8) |
| Outreach | **The founder's own Gmail, connected with Google sign-in (decided Nov 4; replaces Unipile).** We send and read through the Gmail API with the founder's permission: free, no vendor, the creator sees the founder's real address, and every message and reply stays in the founder's Gmail. Google's test mode allows up to 100 users; opening it to everyone needs Google's app verification (a domain and a privacy policy) and, for reading mail, a yearly security assessment (CASA). Outlook later through Microsoft Graph. Until a founder connects Gmail, they paste replies in. A/B test soft vs. concrete-offer first message (§7) |
| Contact finding | **Free sources only (decided Nov 14).** The creator's bio on every linked account, their link-in-bio page and their own website (contact pages too), checked by Jev; no paid email finders or verifiers, no getting past YouTube's captcha-gated email button. No email → one-click DMs (Instagram, X and LinkedIn don't allow safe automated DMs to strangers, so we never send DMs for the founder) (§7.1) |
| Agent autonomy | **The agent proposes; the founder chooses per step what may run on its own (decided Nov 4, revised the same day).** A per-campaign setting: follow-ups and late-post nudges can be set to automatic once Gmail is connected; anything with money or terms (counters, agreeing, marking paid or lost) always waits for approval. Default: everything waits. Bulk review: select several suggestions, edit any, "Approve selected". Every action is logged (§7.8) |
| Results v1 | **Links + promo codes + views (decided Nov 4).** Our own short link and a promo code per creator, views on days 1–60 from the platform, cost per view and per click against the forecast. Signups and sales come next (§8.4–8.5) |
| UI | **One look everywhere (decided Nov 4)**, written down in `docs/UI_GUIDE.md` with shared controls in `frontend/components/ui/` and `frontend/lib/ui.ts`. No browser-native dropdowns |
| Tabs and chat | **Brief · Leads · Outreach · Track (decided Nov 5).** Outreach and Deals become one Outreach tab: every creator is one chat from the first pitch to agreed (pitches drafted in bulk into each chat, reviewed, then sent); the channel (email, Instagram DM, WhatsApp) is a chip per chat and the screen is the same for all. The agent's draft sits in the message box; a You / creator switch adds pasted DMs. After agreeing, a request for more keeps the deal agreed and the founder chooses hold or accept. Alerts: in-app counts, a bell across campaigns, title count, browser notifications while open. Track is its own tab (§7.6): one page with goal and forecast, posts found automatically, creators ranked, results from tracking links, codes and an optional signup snippet, comment summary, and a To pay list (ReachAI never moves money). Shipped in three PRs: chat (done), one Outreach tab, Track |
| Agent access | **Remote MCP server** inside the backend. Typed tools, not one natural-language tool. **The user's agent writes text, our server supplies facts and checks the result.** Clerk OAuth plus personal API keys. Nothing sends or moves money over MCP in v1 (§15) |

### Core principle (kept from the current version)
Cheap filters first, expensive work last. Everything is batched, cached and resumable. The LLM only sees the final shortlist, and only to **write** text.

```
Code / API  →  Statistics / ML  →  Jev (judgments)  →  Code (scoring)  →  LLM (brief + pitch)
   free            ~free              ~$0.01/run           free            top-N only
```

---

## 1. Current state (what exists today)

**Discovery** (`backend/app/my_agent/`, removed Nov 4; kept here as the starting point), YouTube only. LangGraph runs these steps in sequence:
`campaign_understanding (LLM)` → `keyword_generator (LLM)` → `youtube_search_gate` → `subscriber_filter` → `channel_enrichment` → `semantic_processor (embeddings + BM25, top 30)` → `reranker_node (LLM, batches of 15)` → `final_scoring_node (0.6·fit + 0.4·health)` → `llm_reasoning_node (LLM, top N)`.

**Outreach** (`backend/app/outreach/`): one branch per creator, generate (LLM) → rule-based validation → at most 1 repair → collect. Uses a Postgres checkpointer, Inngest Realtime progress, and LangSmith evals (`backend/OUTREACH_EVALUATION.md`).

**Gaps:**
- Email is only found by regex over descriptions.
- Sending, the inbox, sequences, deals and tracking don't exist.
- `users.credits` exists but nothing charges against it.
- `Transaction` is unused.
- The Instagram button in `MultiPlatform.tsx` is disabled.
- The models are hard-coded to Gemini, which has availability problems.
- YouTube quota (`search.list` = 100 units) caps us at roughly 10 runs per day.

---

## 2. Target architecture

```
                          ┌───────────────────────── Frontend (Next.js) ─────────────────────────┐
                          │ Campaign brief · Results · Outreach · Inbox · Pipeline · Billing      │
                          └──────────────┬───────────────────────────────────────▲───────────────┘
                                         │ REST                                  │ Inngest Realtime
┌────────────────────────────────────────▼───────────────────────────────────────┴──────────────┐
│ FastAPI                                                                                        │
│  routes: campaign · outreach · inbox · deals · billing · connections · webhooks               │
├────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Inngest functions (durable): discovery run · outreach gen · sequence steps · refresh jobs      │
├──────────────┬───────────────────┬────────────────────┬───────────────────┬────────────────────┤
│ Discovery    │ Platform adapters │ Judgment layer     │ LLM layer         │ Billing            │
│ graph        │ youtube · x ·     │ app/judge/ (Jev)   │ app/llm/ (gateway │ app/billing/       │
│ (generic)    │ instagram ·       │ questions.py       │ wrapper, routes)  │ credits ledger,    │
│              │ linkedin          │ constants.py       │                   │ Dodo Payments      │
├──────────────┴───────────────────┴────────────────────┴───────────────────┴────────────────────┤
│ Postgres: users · campaigns · creators · creator_snapshots · judgments · outreach_* · deals ·  │
│           credit_ledger · cost_events · subscriptions · connected_accounts                     │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
External: YouTube API · X provider · Apify · LangSmith Gateway (Groq/Cerebras/OpenAI/…) · Jev ·
          Gmail API (founder inboxes) · email verifier · Dodo Payments
```

### New backend packages
```
backend/app/
  llm/            client.py (gateway wrapper), routes.py (task → route name)
  judge/          client.py (Jev), questions.py, constants.py, combine.py
  platforms/      base.py (adapter Protocol), youtube.py, x.py, instagram.py, linkedin.py
  metrics/        robust.py, momentum.py, anomaly.py, valuation.py, baselines.py
  discovery/      graph.py (generic), nodes/*.py   (replaces my_agent/ after migration)
  creators/       repository.py (cache + DB), refresh.py
  billing/        ledger.py, constants.py, dodo.py, grants.py
  messaging/      unipile.py, sequences.py, inbox.py, classify.py, verify_email.py
  deals/          service.py, negotiation.py, tracking.py
```

---

## 3. Phase 0: Foundations (LLM gateway, Jev client, config)

### 3.1 LLM layer: LangSmith LLM Gateway behind a wrapper
**Why a wrapper:** the gateway is in beta, its fallback chains only accept OpenAI-compatible endpoints, and its pricing for bring-your-own-key use isn't confirmed. Nodes must never import a provider SDK directly.

```python
# app/llm/client.py  (sketch)
def chat(route: str, messages, schema: type[BaseModel] | None = None, **kw) -> BaseModel | str
async def achat(route: str, messages, schema=None, **kw)
```
- Implementation: an OpenAI-compatible client pointed at the gateway's base URL. `route` maps to a named gateway route that holds the fallback chain.
- `schema` → structured output. Validate with Pydantic; on failure retry once, then move to the next route.
- Every call records tokens and cost into `cost_events` (§7.4).
- Escape hatch: `LLM_BACKEND=gateway|openrouter|direct` env var.

### 3.2 Model routing (one place: `app/llm/routes.py`)
| Task | Route name | Primary | Fallbacks | Why |
|---|---|---|---|---|
| Campaign strategy + keywords (merged, 1 call per run) | `strategy` | Frontier model (chosen by eval) | 2nd frontier → gpt-oss-120b | Everything downstream depends on it; 1 call, so cost is irrelevant |
| "Why this creator" brief (top N) | `brief` | gpt-oss-120b (Groq) | gpt-oss-120b (Cerebras) → Gemini Flash | Short, fast, grounded on Jev's answers |
| Pitch generation + repair | `pitch` | Best writing model (chosen by eval) | 2nd frontier | Read by creators; reply rate depends on it |
| Reply drafts / negotiation | `reply` | Same as `pitch` | — | Tone and judgment |
| Offline eval judge | `judge_eval` | A different model family from `pitch` | — | Independence |
| Fit-scoring fallback (only if Jev is down) | `fit_fallback` | gpt-oss-120b | Gemini Flash | Keeps runs alive |
| Embeddings | direct (not the gateway) | `gemini-embedding-001` | an OpenAI embedding model | The gateway may not proxy embeddings; verify |

The model for each route is picked with the **existing LangSmith eval suite** (`backend/tests/evals/`) on the same dataset. Record the winners in `routes.py` along with the eval run ID.

### 3.3 Jev client (`app/judge/client.py`)
- Uses `typesafe_sdk` (Python). The key comes from the `TYPESAFE_API_KEY` env var only; never pass it in code.
- **Provider:** a TypeSafe key goes to TypeSafe directly (pinned `jev-1.13.0`); an OpenRouter key (`sk-or-...`) goes through OpenRouter's Jev gateway (`https://openrouter.ai/api`, pinned `typesafe/jev-1.14-20261014`). `JEV_PROVIDER` / `JEV_MODEL` override. Cost rows are logged under the provider used.
- **Pin the model** `jev-1.13.0`, and log `response.model` together with `usage.input_tokens`.
- Concurrency ≤ 8 workers per key. Account limits are about 1,200 requests/min and 250k tokens/s.
- Use the SDK's `RetryPolicy` for 429/5xx; don't write a custom retry loop.
- **Fallback:** if Jev fails for a batch, call the `fit_fallback` LLM route with the same questions as a JSON schema and mark the result `judge_source="llm_fallback"`.
- All questions, thresholds and weights live in `app/judge/constants.py` and `questions.py`. Those are the files humans review and tune.

### 3.4 Config / env additions
```
LLM_BACKEND, LANGSMITH_GATEWAY_URL, LANGSMITH_API_KEY (existing)
TYPESAFE_API_KEY
X_PROVIDER=twitterapi|official, X_PROVIDER_API_KEY, X_OFFICIAL_BEARER
APIFY_TOKEN
UNIPILE_DSN, UNIPILE_API_KEY
EMAIL_VERIFIER_API_KEY
DODO_PAYMENTS_API_KEY, DODO_PAYMENTS_WEBHOOK_KEY, DODO_PAYMENTS_ENVIRONMENT=test_mode|live_mode, DODO_PRODUCT_IDS (JSON, live only)
```

---

## 4. Phase 1: Shared core (creator model, adapters, generic graph)

### 4.1 `CreatorProfile`: one shape for every platform
```python
class Post(TypedDict):
    post_id: str
    url: str
    text: str                 # title for YouTube, caption for IG, post text for X/LinkedIn
    published_at: datetime
    views: int | None         # LinkedIn: None (not public)
    likes: int
    comments: int
    shares: int | None
    is_short_form: bool       # Shorts / Reels

class CreatorProfile(TypedDict):
    creator_id: str           # our UUID
    platform: Literal["youtube", "x", "instagram", "linkedin"]
    platform_id: str          # channel id / user id / username / public profile slug
    handle: str
    display_name: str
    bio: str
    url: str
    followers: int
    country: str | None       # platform value if available, else from Jev (any platform without a listed country)
    language: str | None
    external_links: list[str]
    contacts: dict            # {"email": [...candidates], "business_email": ..., "booking_url": ...}
    cross_links: dict         # {"instagram": ..., "x": ..., "youtube": ..., "linkedin": ...}
    recent_posts: list[Post]  # 12–20 most recent
    fetched_at: datetime
    source: str               # "youtube_api" | "twitterapi" | "apify:<actor>" ...
```
Downstream nodes (metrics, Jev, scoring, outreach) read **only** this shape.

### 4.2 Platform adapter interface (`app/platforms/base.py`)
```python
class PlatformAdapter(Protocol):
    platform: str
    async def source_candidates(self, strategy: Strategy, limits: Limits) -> list[CandidateRef]
    async def fetch_profiles(self, refs: list[CandidateRef]) -> list[CreatorProfile]   # cache-aware
    def cheap_filter(self, ref_or_profile, constraints) -> bool                          # code only
    def platform_priors(self) -> PlatformPriors   # CPM, CTR, ER norms per follower tier
    def estimate_cost(self, limits: Limits) -> float                                   # USD, for credits
```

### 4.3 Generic discovery graph (`app/discovery/graph.py`)
| # | Node | Kind | Output |
|---|---|---|---|
| 1 | `strategy` | LLM, route `strategy`, **1 call** (merges today's two calls) | topics, pain points, formats, platform-specific queries/hashtags, `trend_topics`, primary metric, safety level |
| 2 | `source` | **Discovery ladder** (§4.9) across selected platforms, in parallel; extra sources (§4.10) | Candidate refs, deduplicated across queries and platforms, with `found_via` |
| 3 | `cheap_filter` | Code | Drops by follower range, country (if the platform provides it), posting recency |
| 4 | `fetch` | Adapter + creator cache | `CreatorProfile[]` |
| 5 | `metrics` | Stats / ML (§4.5) | Metrics, anomaly score, health gates |
| 6 | `semantic_recall` | Embeddings + BM25 (existing logic) | **Top 100** (was 30) |
| 7 | `judge` | **Jev** (§4.6), 1 request per creator, ≤ 8 workers | Typed answers |
| 8 | `score` | Code (§4.7) | `final_score`, `deal_status`, breakdown |
| 9 | `brief` | LLM, route `brief`, top N only, fed with Jev's answers | `llm_reasoning` |

Inngest stage events keep the current names where they map, plus new ones (`judge`, `metrics`). `WorkflowStatus.tsx` reads the list of stages from the backend.

### 4.4 Creator database and cache
**Tables:**
```
creators(creator_id PK, platform, platform_id, handle, display_name, bio, url, followers,
         country, language, contacts JSONB, cross_links JSONB, niche, last_fetched_at,
         data_expires_at, UNIQUE(platform, platform_id))
creator_snapshots(snapshot_id PK, creator_id FK, captured_at, followers, recent_posts JSONB,
         metrics JSONB)                         -- time series → real growth rates later
creator_judgments(judgment_id PK, creator_id FK, campaign_id FK, jev_model, questions_version,
         answers JSONB, input_tokens, created_at)
```
**Cache rules:**
- Reuse the profile and follower data if `last_fetched_at` is under 7 days old.
- **Always** fetch fresh recent posts on a run. This is what makes trend detection work.

**⚠ Compliance:**
- YouTube API Services policies require stored API data to be refreshed or deleted after 30 calendar days (checked Nov 4).
- Implementation: `data_expires_at = fetched_at + 30d` for YouTube rows, plus a nightly Inngest cron that refreshes or deletes expired rows.
- The same job enforces deletion requests (GDPR/DPDP). *(Not built yet: roadmap K18.)*

**As built (Nov 4, `app/creators/refresh.py`, Inngest cron `refresh_youtube_data` daily 09:17 UTC):** policy checked Nov 4: stored YouTube API data must be refreshed or deleted after 30 calendar days.
- Refresh = creators due within 2 days that are *useful* (scored in a run, or in a campaign's results or saved leads), plus creators in results over 30 days old that aren't stored (the old engine never stored them). Capped at 1,400 creators a night (~1,460 quota units).
- Delete = due creators that weren't refreshed, once expired; and channels YouTube no longer returns (only when the fetch had no errors, so a quota or network failure never deletes useful creators).
- Snapshots older than 30 days are deleted; `run_candidates.metrics` older than 30 days is cleared.
- LangGraph checkpoint threads whose newest checkpoint is over 30 days old are deleted (any graph); checkpoints are only needed to resume a run in progress.
- Results (`campaigns.campaign_leads`, `saved_leads.lead_data`) older than 30 days (`data_as_of`, else the campaign/saved date): YouTube fields are rebuilt from the refreshed data; if the creator couldn't be refreshed, only name, link and our scores/reason stay and the lead is marked `data_expired` (the UI hides its numbers).

### 4.5 Metrics: statistics and ML instead of hand formulas (`app/metrics/`)
Computed per creator from `recent_posts` (long-form and short-form kept separately):

| Metric | Formula | Replaces |
|---|---|---|
| `median_views` | median(views) | mean(views) |
| `reliability` | MAD/median → High < 0.35, Medium < 0.8, else Low; Instagram bands × 1.3 (reel views swing more) | std/mean |
| `engagement_rate` | median((likes + comments) / views); IG without views: / followers | sum ratio |
| `er_percentile` | Percentile of ER within (platform, follower tier, niche) from `creators` | fixed 0.5% floor |
| `momentum` | median(views of the newest 5) / median(views of posts 6–15) | none |
| `outperformance` | median(newest 5 views) / followers | none |
| `posting_cadence` | median days between posts; `days_since_last_post` | inactive > 180 days |
| `anomaly_score` | IsolationForest (§ below) | comments/likes × 5000 "trust" |
| `valuation` | median_views / 1000 × CPM(platform, industry, geo) | same idea, robust input |
| `forecast_clicks` | median_views × CTR(platform, industry) | same |

- **Rising creator:** `momentum ≥ 1.5` and `days_since_last_post ≤ 14`, or `outperformance ≥ 1.0` for nano/micro creators (under 100k followers; a stand-in for "below the tier median" until peer data exists). Shown as a badge, and adds a scoring bonus (§4.7).
- **Trend-relevant creator:** the Jev Noul `posts_on_trend` (§4.6) is above 0.6 for any of the newest 5 posts.
- **Anomaly model** (`app/metrics/anomaly.py`):
  - **Features:** log(followers), ER, comments/likes, views/followers, coefficient of variation of views, coefficient of variation of posting intervals, and on LinkedIn, comment-author repetition when available.
  - **Model:** one `IsolationForest(contamination=0.05)` per platform, refit nightly once `creators` has at least 500 rows for that platform. Until then, use rule thresholds from `platform_priors()`.
  - **Output:** `anomaly_score` in [0, 1]. Above 0.8 → excluded; 0.6–0.8 → shown with a "Suspicious engagement" warning.
- **Baselines** (`baselines.py`): percentile tables are recomputed nightly from `creators`. Before there are 200 rows per group, use the static priors.
- **LinkedIn valuation:** impressions aren't public. Prior = median transacted price by follower tier (Favikon, from 135 deals: median $798; Naano: €84–720 by tier). Calibrate once our own deals record real rates (§9).
- **Later (once data exists):** LightGBM LambdaRank on metrics plus Jev probabilities, with labels from user behaviour (§11).

### 4.6 Jev judgments (`app/judge/questions.py`)
**State shape** (only what the questions need). Untrusted creator text stays in its own fields:
```json
{
  "brief": {"product": "...", "category": "...", "persona": "...", "pain_points": ["..."],
            "languages": ["en"], "safety_level": "high", "trend_topics": ["..."]},
  "creator": {"platform": "x", "display_name": "...", "bio": "...",
              "recent_posts": ["post text or title 1", "..."]}
}
```
**Questions, all sent in one request per creator:**

| ID | Type | Instruction (as sent) | Used for |
|---|---|---|---|
| `topic_fit` | Score | "How closely do `creator.recent_posts` match the subject of `brief.product`?" Levels: 0 "Posts are about unrelated subjects" · 1 "Same broad field, but a different topic than `brief.product`" · 2 "Some posts cover topics a buyer of `brief.product` cares about" · 3 "Most posts cover topics a buyer of `brief.product` cares about" · 4 "Posts regularly cover the exact problem `brief.product` solves" | fit |
| `audience_stage` | Score | "Who appears to be the audience of `creator.recent_posts`, compared with `brief.persona`?" Levels: 0 "A clearly different group from `brief.persona`" · 1 "Same broad group, wrong experience level" · 2 "Overlaps with `brief.persona` in part" · 3 "Matches `brief.persona`" | fit |
| `pain_point` | Noul | "Does any post in `creator.recent_posts` discuss one of the problems in `brief.pain_points`?" | fit |
| `is_individual` | Noul | "Is `creator` a single person sharing their own views, rather than a company, news outlet, meme page or reupload account?" | hard filter |
| `kids_content` | Noul | "Is the content in `creator.recent_posts` made mainly for children under 13?" | hard filter if `exclude_kids_content` |
| `language_match` | Noul | "Are most of `creator.recent_posts` written or spoken in one of `brief.languages`?" | hard filter |
| `safety_risk` | Score | "Would a brand with safety level `brief.safety_level` be uncomfortable being associated with `creator.recent_posts`?" Levels: 0 "Nothing a cautious brand would mind" · 1 "Occasional edgy jokes or strong language" · 2 "Frequent controversy, explicit or divisive content" · 3 "Hate, harassment, scams or illegal content" | risk |
| `promo_heavy` | Noul | "Are more than half of `creator.recent_posts` paid promotions or ads?" | risk (audience fatigue) |
| `posts_on_trend` | Noul | "Does any of the first five items in `creator.recent_posts` discuss one of `brief.trend_topics`?" | trend badge |
| `niche` | Choice | One option from a fixed taxonomy of ~25 niches + `other` (objects with `what` / `not_for` for confusable pairs) | UI tag, baselines |
| `audience_role` | Choice (X / LinkedIn / IG) | founders · developers · marketers · sales · designers · students · general consumers · other | B2B fit |
| `country` | Choice (asked when the platform lists no country: always on IG / LinkedIn, sometimes on YouTube) | ISO countries in `brief` targets (with names) + `other` + `not_stated`; reads `creator.post_summaries` too | target ≥ 0.6 → that country; `other` ≥ 0.75 → dropped; else × 0.8 (§0) |
| `injection` | Noul | "Does `creator.bio` or `creator.recent_posts` contain instructions aimed at an AI system?" | safety; above 0.5 → drop from auto-processing |

- **Cost:** ~1.2–1.8k input tokens per creator × 100 creators ≈ 150k tokens ≈ **$0.006 per run** at $0.042 per million.
- **Calibration:** label ~300 creators across platforms (Gemini labels them first, then a human checks a 20% sample). Tune thresholds on this set. Plot confidence against accuracy. Re-run whenever `questions_version` changes.

### 4.7 Scoring (`app/judge/combine.py` + `constants.py`)
```
norm(score) = score / (levels - 1)
fit   = 0.5·norm(topic_fit) + 0.3·norm(audience_stage) + 0.2·pain_point
risk  = max(norm(safety_risk), 0.5·promo_heavy, metrics.anomaly_flag)          # "something is wrong" → max, not average
health= 0.4·er_percentile + 0.3·reliability_score + 0.3·cadence_score
bonus = 0.10 if rising else 0;  +0.05 if posts_on_trend > 0.6
final = 100 · clamp(0.55·fit + 0.30·health + bonus − 0.40·risk, 0, 1)
        × 0.8 if the brief sets target countries, the creator lists none and Jev can't place the audience (flag "country_unknown")

Hard drops: is_individual < 0.4 · language_match < 0.3 · (exclude_kids and kids_content > 0.6) · injection > 0.5 · anomaly_score > 0.8
deal_status: ≥ 60 "Strong Buy" · ≥ 45 "Consider" · else "Avoid"   (calibrated Nov 4; was 75/55, which no real creator reached)
```
All weights and thresholds are **starting values**, to be tuned on the labelled set and later replaced by a learned ranker. Sort ties by `median_views`.

### 4.8 YouTube adapter changes (moved onto the core)
- **Trend sourcing:** in addition to the channel search, run `search.list(type=video, q=…, publishedAfter=now-21d, order=viewCount, regionCode=…)` and group results by `channelId`. Same quota cost per call.
- Optional: `videos.list(chart=mostPopular, videoCategoryId=…, regionCode=…)` costs 1 unit and shows what's trending in a category.
- **Quota:** request a quota extension (YouTube API compliance audit). Until then, keep total searches per run ≤ 8 and cache channel data.
- Replace the in-memory `checkpointer` in `my_agent/agent.py` (unused in production; the runtime already uses Postgres) when the module is removed.

### 4.8b YouTube adapter as built
- **Unknown country is kept, not dropped.** The old pipeline dropped channels with no country set; many real channels leave it blank, so a target-country filter now only drops channels that *state* a different country. They are ranked lower and labelled instead (§4.7).
- **Searches (revised Nov 4 after the old-vs-new comparison):** short 2-5 word niche phrases; a quarter of the budget (at least one) on recent-video trend search, the rest on channel search; the top-up round is an all-time video search by relevance. Long sentence-like phrases and `order=viewCount` returned 0-17 results for niche B2B topics.
- **Rate limits:** `rateLimitExceeded` is treated like `quotaExceeded` (YouTube sends it once the daily search allowance is gone): stop calling YouTube for the run, one warning. YouTube's day resets at midnight Pacific time.
- **Candidates are ranked by reciprocal rank fusion** (score = Σ 1/(60 + rank) over the searches a channel appears in): channels several searches agree on come first, and each search's top results still rank high, so trend results aren't crowded out (replaced round-robin, Nov 4).
- **Every candidate gets the cheap channel check** (1 unit per 50, up to `max_candidates`); only the best `max_profiles` that pass get recent videos fetched (~1 unit each). Before, candidates past `max_profiles` were never checked at all. Skipped ones are recorded as "over the measuring limit for this run".
- **Video details are batched across creators** (50 ids per call), not one call per creator.
- **Shorts** = duration ≤ 180 s (YouTube Shorts can be up to 3 minutes).
- Contacts come from the **channel description only**, never from video descriptions (fixes the old "first email in any description" problem). The API doesn't expose the channel's links section (roadmap K11).
- First real recording (Nov 3): YouTube engagement priors were too high for large education channels (~1-2% is normal), so they were lowered.

### 4.9 Platform selection and the cheapest-first discovery ladder

**Platform selection** (runs once per campaign):
0. **User choice wins (built Nov 4):** if the brief has `campaign.platforms`, exactly those are searched (full mode), with no Jev check and no probes; unbuilt ones produce a warning. An empty list means steps 1-3 below.
1. **Preset** by founder type, set in the brief: `b2b` → {youtube, x, linkedin}; `consumer` → {youtube, instagram}.
2. **AI check:** one Jev request with a Noul per platform: "Would buyers of `brief.product` (described in `brief.persona`) follow creators on {platform} for this topic?" A platform is **added** if its Noul is above 0.7, and flagged "low fit" if it's below 0.3. Cost < $0.001.
3. **User toggle** on the brief form, which shows the preset + AI suggestion and the credit estimate per platform.
4. Output: `platform_weights {platform: 0..1}`. Used for sourcing budget (below) and as a small scoring prior.

**Discovery ladder.** Each rung runs only if the rungs before it didn't fill the target:

| Rung | Source | Cost | What it gives |
|---|---|---|---|
| 1 | **Creator DB**: vector search (pgvector) over stored creators' bio + recent-post embeddings, filtered by selected platforms, constraints and freshness | ~$0 | Instant results for niches we've seen before |
| 2 | **YouTube search** (channel + recent-video search, §4.8) | Quota only | Rich data, public views, links to other socials |
| 3 | **Expand through creators' own links**: follow cross-links from rung 1–2 creators to their accounts on the *selected* platforms; fetch those exact profiles | Cheap (profile fetch, no search) | Verified multi-platform creators |
| 4 | **Native gap-fill search** on a selected platform, only if it still has fewer than `target_per_platform` qualified candidates; search size scales with the gap | Paid | Platform-only creators, rising creators, trends |

- `target_per_platform = ceil(creator_count × 10 × platform_weight)` qualified candidates, meaning they passed `cheap_filter` + metrics gates.

**Quality rule: probe, then expand.** Stopping when there are *enough* creators can miss *better* ones, so rung 4 is decided by quality, not count:
1. **Probe:** run 1–2 native queries on **every selected platform** (`probe_queries = 2`, ~10% of a full search's cost), even when rungs 1–3 filled the target.
2. Score the probe candidates with the same pipeline (metrics → Jev → score).
3. **Expand rule:** run the full native search on platform P if **any** probe candidate on P would enter the current top `creator_count`, i.e. its score is above the current top-N cutoff (`expand_margin = 0`). Otherwise stop on P.
4. **Quality floor** (safety net): if the mean `fit` of the current top N is below `FIT_FLOOR = 0.55` (to be tuned), expand on all selected platforms regardless.
5. **"Search deeper"** button in the results: the user can pay the credits to expand any platform. The UI shows what was searched ("LinkedIn: probe only, nothing better found").

**Fair comparison across platforms.** `health` uses **percentiles within each platform** (and follower tier), never raw counts. Otherwise YouTube's larger numbers would always win. Fit comes from Jev and is the same scale on every platform.

**Learned probe sizes.** Store `platform_win_rate[niche][platform]`, the share of runs where a creator found on that platform ended in the final top N. Once a group has ≥ 30 runs: platforms that often win get `probe_queries = 3`, and platforms that never win (< 5%) get 1. Recompute nightly.

**Recall benchmark (required before launch, then monthly).** On ~30 real briefs, run the ladder **and** a full search on every selected platform. Metric: the share of the full search's top 10 that the ladder also found. **Target ≥ 90%.** Tune `probe_queries`, `expand_margin` and `FIT_FLOOR` until it's met. Track it as a dashboard metric.
- **Reverse expansion:** creators found by native search also expose links (X bio → YouTube, Instagram → website). Follow them the same way, so the person record fills in.

**Identity and the person model.** One person can own several accounts:
```
creator_persons(person_id PK, display_name, primary_contact JSONB, created_at)
creators.person_id FK → creator_persons        -- one row per platform account (existing table)
person_links(person_id, creator_id, link_source [self_link, reverse_link, name_match],
             confidence, verified_at)
```
- **self_link** (the account links to the other account itself) = verified, confidence 1.0.
- **name_match** (same name/handle, no link) is only *suggested*. It needs a code check (handle similarity, matching avatar hash or website) **plus** the Jev Noul "Do `account_a` and `account_b` belong to the same person?" above 0.85. Otherwise it's never merged automatically.
- The UI shows one card per person: combined reach, per-platform metrics, best contact. Pitches can offer a **bundle** across the person's platforms.
- **As built (Nov 14, F1.17b):** links are read from every account's own bio/description/websites (`identity.links_of`; YouTube links now parsed too). Code rule (`identity.decide`): a link both ways, or a link one way plus a matching name/handle (≥ 0.85, names under 5 letters ignored) → `self_link`, merged. A one-way link to a different name (sponsors, friends) or the same name with no link → Jev `same_person` (≥ 0.85, at most 30 checks per search) → stored as a **suggestion only** ("probably them"), never merged, not counted in total followers. A new graph step `people` (after ranking, before reasons) links accounts, measures the top 10 people's linked-but-unmeasured accounts with the normal adapters (handles resolved: YouTube `forHandle`, X `user_info`), and results are deduped to one per person (best-scoring account). Leads carry `accounts` (main first, then linked / suggested / unmeasured) and `reach_total`. Anyone else's linked account: `POST …/accounts/measure`, free. Any failure in this step is logged and the search finishes without the extra accounts.

### 4.10 Extra discovery sources
| Source | How | Cost | Value |
|---|---|---|---|
| **Competitor sponsors** | Strategy outputs 3–5 competitor names → search YouTube descriptions / X posts for "sponsored by", "use code", "#ad" + competitor → Jev Noul "Is `post.text` a paid promotion of `competitor`?" | Low | Creators proven to accept deals; likely to reply; tells us their price range |
| **Lookalikes** | The user pastes 1–3 creator URLs → fetch and embed them → nearest neighbours in the creator DB + their cross-links → normal pipeline | ~$0 after the DB is warm | Very precise; great for founders who know one creator they like |
| **Founder's own followers** | Optional: connect the founder's X handle → fetch follower IDs (~$0.02 per 5k via a third-party provider) → keep accounts above a follower threshold → normal pipeline | Low | Warm audience that already knows the founder |
| **Pre-warmed trending niches** | Nightly Inngest cron per popular niche (top niches by run count): fetch trending posts on YouTube/X/Instagram, update the creator DB and snapshots | Amortised across users | Near-instant runs for common niches; better rising-creator detection (real time series). Turn on once ≥ 20 runs per niche per week |

Each source becomes an extra **rung-0 input**. Its candidates go through the same filters, Jev judging and scoring, tagged with `found_via` so the UI can show "Promoted a competitor" or "Follows you".

### 4.11 Cost and latency optimisations (built into Phase 1)
| # | Optimisation | Effect |
|---|---|---|
| 1 | Creator DB as rung 1 (pgvector) | Repeat niches are near-free and instant |
| 2 | **Search cache**: `(platform, query, region, window)` → results, TTL 24–72 h | No paying twice for the same search |
| 3 | **Early stop**: stop sourcing once `target_per_platform` is met | No over-fetching |
| 4 | **Bio-only Jev gate before paid post fetch** (`is_individual`, rough `topic_fit` on bio) | Skips obvious misses before Apify / X post fetches |
| 5 | **One provider job per batch** (Apify actor run with all usernames; batched X lookups) | Avoids per-run startup time and minimum charges |
| 6 | **Content-hash caches** for embeddings and Jev answers: key = hash(creator content) + hash(brief) + `questions_version` | Never pay twice |
| 7 | **Lazy work**: "why this creator" brief and contact finding only for creators shown or opened | Fewer LLM calls and verifier calls |
| 8 | **Prompt caching** for pitches (shared campaign context prefix) where the provider supports it | Lower pitch cost and latency |
| 9 | **Platforms in parallel** (LangGraph `Send` per platform) | Total time ≈ slowest platform, not the sum |
| 10 | **Incremental refresh** on re-runs: fetch only posts newer than the last snapshot | Faster, cheaper re-runs |
| 11 | YouTube quota discipline: ≤ 8 searches per run; `playlistItems` / `videos.list` batched (1 unit per 50 IDs) | More runs per day |

### 4.12 Streaming results
- The pipeline publishes results **per rung**: DB and YouTube results appear first (~20–40 s), then expansion and native results.
- Inngest Realtime topic `campaign:{run_id}` / `leads`, payload = scored creators (delta) + `is_final=false|true`.
- UI: show a "More creators arriving…" bar. Rows don't reshuffle while the user is reading; new rows are inserted below with a "New" chip. A final **"Re-rank"** happens when `is_final` arrives (one animation, with a toggle to keep the order).
- Credits are committed at the end, per §5.3.

### 4.14 Run execution model (decided, revised Nov 3)
**Decisions:** LangGraph runs the pipeline and makes it durable inside a run; Inngest starts, retries, limits and cancels runs. Platforms run as parallel LangGraph branches in one run. Re-running a campaign cancels the previous run. Limits: 2 runs per user, 5 at once overall (Inngest free-plan maximum; changed from 10 on Nov 4 because syncs failed). Backend stays on Vercel; caches in Postgres.

**Why (checked in code, Nov 3):** the old runner re-sent the input on every Inngest retry. In LangGraph that starts a new run from the first step and duplicates accumulated state (a test showed `['a','a','b']`), so the Postgres checkpoints were saved but never used. Resuming needs `None` as the input. The old runner also used one thread per campaign (so runs shared history), marked the campaign failed before Inngest retried, and used `InMemoryCache`, which doesn't survive between serverless requests.

**Run lifecycle**
```
campaign/run (event id = run_id)  ->  discovery/run  [concurrency: 2 per user, 5 per account (plan max); singleton key=campaign_id mode=cancel;
                                                      retries 3; timeouts.finish 15 min; cancel on campaign/cancel; on_failure handler]
   thread_id = run_id
   checkpoint with pending steps?  yes -> astream_events(None)   (resume)
                                   no  -> astream_events(brief)  (fresh)
   durability = "sync"   (each step's checkpoint is saved before the next starts)
   on error: re-raise; Inngest retries and the retry resumes. on_failure marks the campaign failed after the last retry.
```

**Graph** (`app/discovery/graph.py`)
```
START -> [strategy (LLM) | platform_select (preset + Jev) | db_search (embedding -> pgvector)]   parallel
      -> fan_out: Send(platform_branch, {platform, mode})  per selected platform
             full search on preset platforms with a working adapter; probe (2 queries) on the others,
             all running at the same time
      -> platform_branch (subgraph, checkpointed): search -> fetch_measure
                 -> [top_up -> fetch_measure]   conditional, at most once: a full branch that kept fewer than
                    TOPUP_FACTOR (10) x the creators asked for searches again: unused queries first, all-time
                    video search by views (YouTube channel search on sentence-like queries returns few channels)
                 -> shortlist -> judge_score
             streams newly scored creators (custom stream) to the UI
      -> merge_rank (defer=True: waits for all branches)
      -> probe_check (conditional): Send(platform_branch, mode=expand) where a probe creator beats the top-N
             cutoff or the top-N fit is below FIT_FLOOR; else continue
      -> reasons: Send(reason, creator) per top-N creator, in parallel (LLM, cached)
      -> finalize: campaign_leads in the legacy shape, status COMPLETED
```
Node settings: `retry_policy` on every node that calls an API. A failed search becomes a warning so the other branches continue; other errors retry, then fail the step so the Inngest retry resumes from the checkpoint. The whole run has a 15-minute limit (Inngest `timeouts.finish`).

**Reasons** get our verdict (deal status) in the prompt and must agree with it (`reason-v2`); the verdict is part of the reason cache key.

**The only engine since Nov 4** (F1.13): the old pipeline and its switch are removed.

**State stays small:** profiles and posts live in the creator database; the graph state holds creator ids plus small score records, so checkpoints stay fast.

**Caching:** a LangGraph node cache backed by `cache_entries` (Postgres) replaces `InMemoryCache`, plus the creator-database caches (profiles, Jev answers, embeddings), the search cache, and strategy reuse for an identical brief.

**Request speed (Nov 4):** read endpoints select only the columns they show; the campaign list counts leads in Postgres; the leads endpoint passes the stored JSON through as text; ownership checks select ids only; no endpoint opens extra DB connections; heavy modules (LangGraph, outreach graph) are imported only inside the runs that need them; Fluid compute plus a 5-minute keep-warm Inngest cron avoid most cold starts.

**Concurrency and batching** (all limits in `app/discovery/limits.py`)
| Resource | Limit |
|---|---|
| Runs | 2 per user, 5 per account (Inngest free-plan maximum; 10 made every sync fail) |
| YouTube | 4 searches at once; lookups 20 at once, 50 ids per call |
| Jev | 8 at once per process; 1 request per creator with all questions |
| LLM | reasons in parallel, 5 at once |
| Embeddings | batches of 100 |

**Tables:** `run_strategy(run_id, strategy, platform_weights)` and `run_candidates(run_id, creator_id, platform, found_via, mode, stage, metrics, fit, health, risk, final_score, deal_status, flags, drop_reason)` for streaming, status and debugging.

**Switch-over (done Nov 4):** the old pipeline and the `DISCOVERY_ENGINE` setting are removed; every run uses this graph.

### 4.13 Frontend (Phase 1)
- `MultiPlatform.tsx`: enable platforms based on a flag from the backend (`/platforms` endpoint).
- Lead table and detail sheet:
  - Badges: platform, rising, trend, suspicious engagement.
  - Show fit / health / risk breakdown and the Jev answers in plain language: "Audience: developers (0.82)".
- Show the estimated **credit cost** before "Run campaign".

**Competitor promoted, as built (F1.19).** The brief takes `campaign.competitors` (max 10, deduped, ≤ 60 chars) and `campaign.competitor_mode` (`show` | `prefer` | `avoid`, default `show`); empty competitors fall back to the strategy's competitor list. Both are left out of the brief hash, so cached strategy and Jev answers are reused. `app/metrics/competitors.py` counts a post only when it's sponsored and the named sponsor (or, with no named sponsor, a whole-word mention) is a competitor: code only, no Jev. `combine.score_creator` adds the `competitor` flag; `prefer` adds `COMPETITOR_BONUS` (0.06), `avoid` drops with "recently promoted a competitor (Brand)". The lead carries `competitor_promos: [{brand, posts}]`; the UI shows an amber **Competitor** badge and a "Promoted a competitor" filter.
- **Creator panel data (lead v2, built).** Every lead carries the same shape on every platform, computed in code (`app/metrics/posts.py`), no model calls:
  - `posts[]`: up to 12 newest posts, each with `thumbnail_url`, `format`, `reach` (views, else likes), `x_usual` (reach ÷ the creator's median; `None` and `is_new` for posts under 7 days old, which are also left out of the median), `matched_topics` (brief topics whose words appear in the title or the description's opening paragraph, ≥ 60% of the words, plurals folded; later description lines are link lists and are ignored) and `sponsored` (whole-phrase match on "sponsored by", "use code", "#ad"…).
  - `signals`: `posts_checked`, `fit_posts`, `sponsored_posts`, `sponsor_brands`, `median_reach`.
  - `score_parts`: points from fit, health, bonus and risk (negative); their sum × `country_unknown_factor` (when set) is the final score.
  - `trend` (momentum), `verified`, `person_id` (same person on other platforms), `match_terms` (kept so the nightly refresh re-tags refreshed posts).
  - The panel sorts `posts` into **Best match** (most topics matched), **Above their usual** (highest `x_usual`) and **Latest**.
- **Skipped summary.** `GET /api/campaigns/{id}/skipped` groups the run's `run_candidates.drop_reason` into plain buckets (inactive, too few views, too small, wrong country, not an individual creator…), each creator counted once per bucket.

---

## 5. Phase 2: Billing (credits + Dodo Payments)

Decided Nov 12, 2026. Goal: **affordable, not cheap**. Founders pay only to find creators; everything after that is free. Prices sit far below competitors ($150–300/mo) because our cost per search is cents.

### 5.1 What costs credits

**Only creator searches.** Pitches, AI drafts, negotiation, replies, Gmail sending, Track (forecast, comment reads), exports, share links and MCP/agent use are unlimited on every plan, Free included. They cost us under a cent per creator (measured in `cost_events`).

| Search (one platform, up to ~30 ranked creators) | Credits | Our cost (target) | Status |
|---|---|---|---|
| YouTube | **1** | ~$0.02 (LLM + Jev; YouTube quota is free) | live |
| X | **3** | ≤ $1.00 | with F3.1 |
| Instagram | **4** | ≤ $1.50 | with F4.1 |
| LinkedIn | **8** | ≤ $3.00 | with F5.1 |
| "Find more" on an existing campaign | half, rounded up | reuses cached data | |

- Credit prices = measured cost × ~2, rounded. Reviewed quarterly from `cost_events`; a change never applies to a search already started.
- Constants live in `app/billing/constants.py` (`SEARCH_CREDITS`, `FIND_MORE_FACTOR`, plan table), never inline.
- The cost is **always shown before a run** (brief form, "Find more", MCP `start_search`): "Instagram search · 4 credits · you have 18".
- **Quality guarantee:** a search that returns fewer than `GUARANTEE_MIN_CREATORS` (10) creators that pass the filters is refunded automatically (`refund` ledger entry, note in the run).
- Contact finding (F6.1) is free: our own fetches of bios, link pages and websites, plus free DNS-over-HTTPS. No paid finder or verifier (decided Nov 14).

### 5.2 Plans

| | Free | Solo | Pro |
|---|---|---|---|
| Price (USD) | $0 | **$12/mo** | **$29/mo** |
| Price (India) | ₹0 | **₹499/mo** | **₹1,299/mo** |
| Credits | 3 / month | 25 / month | 80 / month |
| Unused credits | expire monthly | roll over 1 month | roll over 1 month |
| Everything else | unlimited | unlimited | unlimited |
| Later | — | — | 3 teammates + inboxes (F1.18c) |

- **Credit packs (never expire, any plan incl. Free):** 10 credits $8 (₹299), 30 credits $20 (₹799).
- **Annual:** 2 months free (Solo $120/yr, Pro $290/yr).
- **No feature gates**: plans differ only by credits (and seats later).
- **Spending order:** monthly credits first (they expire), then rollover, then pack credits.
- Worst case stays profitable: a Solo user spending all 25 credits on LinkedIn ≈ $9 cost vs $12.

**Growth extras in v1:**
- **Welcome credits:** 5 one-time credits at signup (on top of Free's 3/month).
- **Local prices:** INR prices for India (country from the payment provider's checkout; we never guess from IP alone). Other markets later.
- **Referrals:** 10 credits each for referrer and new user, granted when the new user's first search is committed. Limits: only accounts created in the last 7 days can claim, one claim per account, never your own code, 20 referrer grants a year. (Same card or device checks: not built.)
- **Prices include tax** (Dodo `tax_inclusive` on every product, Nov 13): ₹499 and $12 are final; tax is taken out of them.
- Not in v1: annual price lock for early users.

### 5.3 Ledger (replaces the bare `users.credits` and the unused `Transaction`)
```
credit_ledger(entry_id PK, user_id FK, delta INT, bucket ENUM[monthly, rollover, pack, bonus],
              reason ENUM[grant_plan, grant_pack, grant_welcome, grant_referral, grant_free,
                          reserve, commit, release, refund, expire, adjust],
              ref_type, ref_id, created_at)        -- balance = SUM(delta) per bucket, never stored alone
credit_reservations(reservation_id PK, user_id, amount, ref_type, ref_id,
              status [held, committed, released], expires_at, created_at)
subscriptions(subscription_id PK, user_id UNIQUE, plan [free, solo, pro], interval [month, year],
              currency, status [active, past_due, cancelled], provider, provider_subscription_id,
              current_period_start, current_period_end, cancel_at_period_end)
payments(payment_id PK = provider id, user_id, provider, kind [subscription, pack], item,
              amount_minor, currency, status [succeeded, refunded], created_at)
billing_events(event_id PK = provider webhook id, type, user_id, received_at)  -- idempotency
-- subscriptions also stores provider_customer_id (for the portal and to match webhooks)
referrals(code PK, owner_user_id, referred_user_id UNIQUE NULL, granted_at)
```
**Run flow:**
1. **Reserve** the shown cost in one transaction (`SELECT … FOR UPDATE` on the user's balance rows; rejected if too low; a user has at most one held reservation per campaign).
2. Run.
3. **Commit** at the end. Never more than reserved; if the guarantee applies, commit then `refund`.
4. On failure, **release**. A sweeper releases reservations past `expires_at` (Inngest cron).

**Monthly grants** are lazy: on the first billing read after a period starts, expire the old `monthly` bucket (moving up to one month's worth into `rollover` for paid plans, dropping older rollover) and grant the new month. Idempotent per (user, period).

Daily caps per user (`MAX_SEARCHES_PER_DAY`) and the existing MCP cap still apply.

### 5.4 Payments: Dodo Payments (merchant of record)
- **Why:** as merchant of record, Dodo sells on our behalf and collects and files VAT/GST/sales tax worldwide, handles refunds and chargebacks, and supports UPI and INR payouts. Fees (verify at signup): 4% + 40¢ global, 4% + 15¢ India cards/UPI, +1.5% international cards, +0.5% subscriptions. Paddle is the fallback.
- **Our backend owns** plans, credits and entitlements. Dodo only collects money and reports it, so switching providers is a contained change in `app/billing/dodo.py`.
- **Products in Dodo:** Solo monthly/annual, Pro monthly/annual (USD and INR prices), two packs.
- **Checkout:** `POST /api/billing/checkout {product}` creates a Dodo checkout session with `user_id` in metadata and returns its URL. Never trust the browser for amounts.
- **Webhooks** → `POST /api/webhooks/dodo`: verify the signature (Standard Webhooks, `DODO_WEBHOOK_SECRET`), store the event id in `billing_events` first (duplicates are ignored), then:
  - payment succeeded (pack) → `grant_pack`
  - subscription active/renewed → update `subscriptions`, grant the period's credits
  - payment failed → `past_due`, 3-day grace, then back to Free limits (credits already granted stay)
  - cancelled → `cancel_at_period_end`; Free from the next period
  - refund/chargeback → `adjust` the unspent part
- **Customer portal** (Dodo-hosted) for invoices, card changes and cancelling.
- Env: `DODO_PAYMENTS_API_KEY`, `DODO_PAYMENTS_WEBHOOK_KEY`, `DODO_PAYMENTS_ENVIRONMENT=test_mode|live_mode`, `DODO_PRODUCT_IDS` (JSON item → product id; test-mode ids are in `dodo.py`). Test mode until the business checks pass.
- **Built (Nov 12):** overlay checkout (`dodopayments-checkout`, `manualRedirect`, the page polls the balance until the webhook lands); plan changes on an existing subscription go through `change-plan` (upgrade: prorated now, keep the old plan if the charge fails, the difference in credits is added at once; downgrade: from the next billing date, no charge); paid periods follow Dodo's billing dates and a paid plan with no renewal falls back to Free after `RENEWAL_GRACE` (3 days); unused credits roll over (up to the old plan's month) when a paid period renews straight into the next; a refunded pack takes back its unspent credits. Monthly plans only; annual plans are a follow-up.
- **Compliance before going live:** CA confirms GST treatment (export of services via the merchant of record, LUT) and income tax; own domain for the business check; refund policy page.

### 5.5 Frontend
- **Navbar:** left: logo + Campaigns (main tab). Right, in groups: Pricing · Docs (muted, sliding hover pill) | Connect agent (icons only, copies the setup prompt) and New campaign (HoverButton) | one account capsule with credits (opens **Billing and usage**: balance, buckets, history, Manage plan), alerts and the avatar (menu: credits, Billing and usage, API keys).
- **`/pricing`** (public): plans in searches, a calculator that picks the cheapest plan or plan + packs, packs, FAQ. `/billing` redirects here.
- **Checkout:** Dodo's one-page checkout (`feature_flags.single_page`) in the overlay popup. In test mode only `DODO_TEST_USERS` can buy.
- **Before every search:** the cost line and balance next to the Run button; if short, "Buy 10 credits · $8" inline instead of an error.
- **MCP:** `start_search` returns the cost and balance and needs `confirm=true`; a new read tool `credits` shows the balance.
- Docs page `pricing.mdx` + public `/pricing` page.

---

## 6. Phases 3–5: Platform adapters

### 6.1 X (`app/platforms/x.py`): first new platform
- **Provider:** a twitterapi.io-class API (≈ $0.15 per 1k tweets, $0.18 per 1k profiles). `X_PROVIDER=official` switches to the official pay-per-use API ($0.005 per post read, $0.01 per user read). The official API is too expensive for broad discovery (~$90 per run), so use it only for verification if needed.
- **Sourcing:** advanced search with the strategy queries, recent (≤ 21 days), sorted by engagement, filtered on minimum faves → group by author.
- **Fetch:** profile + last 20 posts for the ≤ 150 authors that pass `cheap_filter`.
- **Metrics:** post view counts are public, so views-based valuation works. CPM prior ≈ 20–40% below Instagram. Sponsored post priors: 10K–50K followers ≈ $300–1,500.
- **Contacts:** emails in the bio or pinned post, the link-in-bio page (crawl it), cross-links.
- **Cost target per run:** ≤ $1 (e.g. 3k search tweets + 150 × 20 timeline tweets + 150 profiles).
- **As built (Nov 13):** twitterapi.io (`x_api.py`, 15 provider credits per tweet, 15 minimum per call, 100k = $1; paced to `X_REQUESTS_PER_SECOND`, retries 429). Query text carries `min_faves:30 -filter:replies -filter:retweets since_time:`; 2 pages per query, cached 24 h. Search tweets embed the author, so profiles cost nothing; only `cheap_filter` survivors cost one `last_tweets` page (≈ 20 posts, reposts and replies dropped). Creators from our database are looked up by their timeline. Provider out of credits (402) keeps earlier pages and adds one warning. The strategy prompt writes `x_queries` (strategy-v4). On only when `X_ENABLED=1` and `X_PROVIDER_API_KEY` are set; `live_platforms()` drives billing, quotes and the brief picker. The free provider tier allows 1 request per 5 s, so production needs a topped-up account (20 rps).

### 6.2 Instagram (`app/platforms/instagram.py`)
- **Provider:** Apify (official actors preferred).
  - Profile scraper ≈ $1.60–2.60 per 1k profiles.
  - Hashtag and reel scraper ≈ $1.30–2.30 per 1k results.
- **Sourcing:**
  - Hashtags and keywords from `strategy` → recent and top posts → owner usernames.
  - Plus cross-links from YouTube and X creators already in the database (free).
- **Fetch:** profile (followers, bio, category, business email, external URL) + last 12 posts/Reels.
- **Specifics:**
  - Country isn't exposed, so it comes from the `country` Choice.
  - Reels views vs. followers.
  - The anomaly model catches follow-for-follow and engagement pods.
- **Cost target per run:** ≤ $1.50. The 7-day profile cache is essential.
- **As built (Nov 13):** three batch runs per search through `app/platforms/apify.py` (start → poll `waitForFinish` → dataset; `maxTotalChargeUsd` on every run = planned items × price × 1.2; run ids remembered per actor + input + run so a retried search resumes the same run; cost from `chargedEventCounts`).
  1. `instagram-search-scraper` `searchType=popular`, all queries in one run (20 reels each, $0.0027 per result). Some broad words return `no_items` (still charged one result); those get one `instagram-hashtag-scraper` `resultsType=reels` run (recent reels with views, $0.0026). Hashtag "posts" were rejected: newest posts, mostly 0 likes.
  2. `instagram-profile-scraper` for up to 120 owners ($0.0026 each): followers, bio, links, business category, last 12 posts with likes and comments but **no views**.
  3. `instagram-reel-scraper` for the best 40 that pass `cheap_filter` (private, size, ≥ 30 posts) and post reels: 6 reels each with `videoPlayCount` (≈ 20–25 s per run).
  - Full search ≈ $1.25 on Apify's free-tier prices; a live run took ≈ 45 s. Metrics: a creator whose main format has no views is measured on reels if ≥ 3 have views, else per follower. Strategy writes `instagram_queries` (strategy-v5). On only with `INSTAGRAM_ENABLED=1` and `APIFY_TOKEN`.

### 6.3 LinkedIn (`app/platforms/linkedin.py`): public post search only
- **Provider:** Apify **logged-out** post search actors (≈ $1.20–2.00 per 1k posts). **No logged-in scraping and no fake accounts** (Proxycurl was sued for exactly this and shut down in 2025).
- **Sourcing:** keyword post search (recent) → authors who are people, not company pages (Jev `is_individual`) → their recent public posts.
- **Profile detail is limited:** headline, follower count when shown, and posts. Users can also **paste profile URLs** to score creators they already know.
- **Metrics:** reactions, comments and reposts (no impressions). The anomaly features include comment-author repetition, to detect engagement pods.
- **Valuation:** a transacted-price prior by follower tier (§4.5).
- **Contacts:** emails or booking links in the about section or posts, and the creator's website. Outreach is email-first or assisted (no automated LinkedIn DMs).
- **Cost target per run:** ≤ $3.
- **As built (Nov 13):** HarvestAPI actors on Apify, no cookies or account (`app/platforms/linkedin.py`, same client as Instagram).
  1. `harvestapi/linkedin-post-search`: all queries in one run, 50 posts each, `postedLimit=month`, relevance ($0.002 per post). Company and showcase pages dropped by author type (no Jev call needed); people ranked per query by their best post (likes + 2 × comments + 3 × reposts), then fused across queries.
  2. `harvestapi/linkedin-profile-scraper` without email search ($0.004 per profile), up to 80: followers, connections, headline, about, country code, websites, creator mode.
  3. `harvestapi/linkedin-profile-posts`: 10 posts from the last 3 months for the best 40 that pass `cheap_filter` (≥ 1,000 followers and the brief's range), reposts excluded ($0.002 per post).
  - Full search ≈ $1.72; a live run took ≈ 47 s. Strategy writes `linkedin_queries` (strategy-v6). On only with `LINKEDIN_ENABLED=1` and `APIFY_TOKEN`. Pasted profile URLs and pod detection are F5.2.
  - **Apify free plan (found Nov 13 on production):** HarvestAPI actors return at most 10 results per run for free Apify accounts (an `error` row says so). The client raises `ApifyError(PLAN_LIMIT)` carrying the results it did get; adapters keep them and show one warning. Real LinkedIn searches need a paid Apify plan.

### 6.4 Adapter acceptance criteria (each platform)
- Returns `CreatorProfile` exactly, and passes the shared metrics and Jev nodes unchanged.
- Logs `cost_events` per provider call. A run never exceeds its credit reservation.
- Golden test: 3 recorded fixture runs (stored JSON) → deterministic metrics output. No live calls in CI.
- Feature flag per platform.

---

## 7. Phase 6: Outreach loop (send, follow up, inbox, classify)

**Design premise.** A founder contacts about **15–40 creators** per campaign to sign 3–8. That's an estimate; measure the real rates. This is **not** mass email. Every message is high-stakes and costs only cents, so we spend on correctness and quality, not on saving tokens. Mistakes (wrong person, wrong name, false claims) are the main risk, not cost.

**Errors in today's flow that this phase fixes:**
| Today | Risk | Fix |
|---|---|---|
| `extract_socials` takes the **first** email / IG / X match from the channel description **plus 15 video descriptions** | Sponsor's, guest's or agency's address/handle picked | §7.1 source ranking + Jev pick + sponsor blocklist |
| Greeting uses the channel title | "Hi TechWithTim" | §7.1 first-name resolution |
| Validation checks evidence IDs exist, not that the claims are true | False statements about the creator's content | §7.6 claim check |
| Pitch sees video titles only | Shallow personalisation | §7.2 creator dossier |
| A pitch is written for every available channel | ~3× wasted generation | §7.3 primary channel |
| No cross-campaign memory | The same creator is contacted twice | §7.1 contact ledger + suppression list |

### 7.1 Identity: the right person, the right address, the right name
1. **Email candidates, ranked by source.** Platform business-email field (IG business email, YouTube about text) > link-in-bio page > the creator's own website contact page > channel description > **video descriptions (only if Jev confirms)**.
2. **Sponsor/guest blocklist:** drop domains of brands mentioned with "sponsored by", "use code", "#ad"; drop addresses that appear on many different creators (agency/sponsor addresses, computed from the creator DB).
3. **Jev pick:** Choice over the remaining candidates + `none_of_these`. "Which address in `candidates` is the business contact of the person who runs `creator`? An address belonging to a sponsor, guest or brand mentioned in a post is not their contact." Accept if confidence ≥ 0.8; otherwise mark "needs review".
4. **Verify** with an email verifier (ZeroBounce / MillionVerifier / Reoon). Send only to `valid`; `catch_all` only after user confirmation. Included in every plan while the cost stays under ~$0.01 per creator (§5.1).
5. **First name:** regex candidates from about text, link page, email local part, sign-offs in posts → Jev Choice + `not_stated`. Fallback greeting: "Hi there" (no channel names).
6. **Social handles:** the same ranking; accept cross-links only from the creator's **own** profile fields (self-links, §4.9).
7. **Contact ledger:** `contact_history(user_id, person_id, campaign_id, channel, first_contacted_at, last_outcome)`. Warn before contacting someone the same user already contacted in the last 90 days.
8. **Global suppression list:** `suppression_list(email_or_handle_hash, reason [opt_out, bounce, complaint], created_at)`. Checked before every send, across all users, for opt-outs.

**As built (Nov 14, F6.1, `app/contacts/`).** Runs at the start of each pitch run for the chosen creators (`outreach/runtime._find_contacts`), never during search. Sources: bio on every linked account (`accounts` with status main/linked) > link-in-bio page (`LINK_PAGE_HOSTS`, also gives social links for DMs) > own website (home + up to 2 contact/about pages, else `/contact`), at most 6 pages per creator. Fetches are SSRF-safe (public IPs only, checked on every redirect; 6 s; 600 KB; HTML/text only). Extraction reads `mailto:`, plain text, `[at]`/`[dot]` forms and Cloudflare-protected addresses. Filters (code): junk/no-reply/placeholder, the link service's or a platform's own inbox, sponsor domains (brands from `sponsorship()` on their posts), domains with no MX/A record (Cloudflare/Google DNS-over-HTTPS, free), addresses listed by ≥ 3 other people (ranked last; Jev sees the count). One Jev request per creator: `email` Choice (+ `none_of_these`, accepted ≥ 0.8), `first_name` Choice (+ `not_stated`, ≥ 0.7), `injection` Noul. Without Jev (or on injection) only a bio or link-page address is used and the first name falls back to `greeting_name`. Saved on the lead (`contact`, `first_name`, `socials`), the creator row (`contacts.found`, reused 30 days) and the deal (`contact_email`, unless the founder typed one). `contact_history` (per founder, sha256 of the address; written on every Gmail send; 90-day "contacted before" note) and `suppression_list` (global, sha256; checked before every send). Steps 4 (paid verifier) and 6 are not built by decision.

### 7.2 Creator dossier (research once, reuse everywhere)
`creator_dossiers(person_id, built_at, content_hash, recent_items JSONB, themes JSONB, past_sponsors JSONB, tone_notes, evidence JSONB)`
- Built once per person (cached across campaigns; rebuilt when `content_hash` changes):
  - The last 2–3 videos/posts, with a **transcript excerpt** where available (YouTube captions).
  - Recurring themes and past sponsors (Jev Nouls over posts).
- Every claim the pitch can make must come from `evidence` items with IDs.
- Pitches, follow-ups and reply drafts all read the dossier.

### 7.3 One primary channel per creator
- Pick `primary_channel` in code:
  - Verified business email → **email**.
  - Else X-native creator with open DMs → **X DM** (assisted).
  - Else Instagram → **IG DM** (assisted).
  - LinkedIn creators → email if found, else an assisted message.
- Generate the **primary pitch only**. Secondary-channel copy is generated when a sequence step needs it. This cuts pitch generation by ~60–75%.

### 7.4 Pitch quality
- **Founder voice profile:** the founder edits or writes 1–2 pitches → we store `voice_profile(user_id, examples, style_notes)`. Generation includes 1–2 examples so later pitches sound like the founder.
- **Two first-message styles, A/B tested across all users (decided: data picks the winner):**
  - `soft`: a low-pressure invitation, no price or package details (current behaviour).
  - `offer`: a clear offer type (paid, affiliate or gifting) plus a fair fee range from `valuation`.
  - Assignment: random 50/50 per creator, stored on the pitch (`variant`). Evaluate the reply rate and the positive-reply rate per variant, per segment (B2B vs consumer, platform). Switch the default when one wins by a clear margin over ≥ 300 sends per arm.
- **Plain-text first email:** no links, images or tracking pixel; short subject, written like a 1:1 note.
- Generation still uses LLM route `pitch` with the existing rule validation + at most 1 repair.

### 7.5 Sending from the founder's own Gmail (decided Nov 4: Google sign-in, no vendor)
- Settings → "Connect Gmail" → Google OAuth (scopes `gmail.send` + `gmail.readonly`, offline access) → store `connected_accounts(account_id, user_id, provider, email, refresh_token_encrypted, status, daily_cap)`. The refresh token is encrypted with a key from env vars.
- Cost: free. Google's test mode allows up to 100 named test users; publishing needs app verification (domain, privacy policy, demo video) and, because `gmail.readonly` is a restricted scope, a yearly CASA security assessment. Unipile (was decided earlier) is no longer needed.
- Send with `users.messages.send` (plain text, the founder's own signature); read replies with `users.history.list` polled by an Inngest cron per connected account (Gmail push via Pub/Sub later). Outlook later through Microsoft Graph.
- Without a connected inbox, everything still works: the founder copies the approved message and pastes replies in.
- **Built (Nov 5):** state is HMAC-signed (user, return path, time; 10 minutes); refresh tokens are Fernet-encrypted with `TOKEN_ENCRYPTION_KEY`, or a key derived from `GOOGLE_OAUTH_CLIENT_SECRET` when unset (rotating it means reconnecting). Only threads ReachAI started are read (`threads.get` on the deal's `gmail_thread_id`); replies are stored as `creator_reply` events with the quoted history removed and read once by Jev. Sync runs when the Deals tab opens (at most every 2 minutes per thread) and on an Inngest cron every 30 minutes (not more often: every run wakes the database). A first pitch can also be sent from the Outreach page, which creates the deal. Store `outreach_messages(message_id, pitch_id, person_id, account_id, channel, direction[out,in], provider_message_id, thread_id, subject, body, variant, status, sent_at)`.
- **Approval rule (decided Nov 4, revised):** by default the first message, every follow-up and every reply wait in the "Needs you" queue (§7.8). Per campaign the founder can let follow-ups and late-post nudges send automatically; counters, agreements and payments always wait. Daily cap still applies.
- **Google consent screen "In production", unverified (decided Nov 4):** in Testing mode refresh tokens expire after 7 days; published-but-unverified keeps them (users see Google's "unverified app" screen; still 100 users max until verification).
- **Deliverability guardrails:** ≤ 40 new conversations per inbox per day; randomised gaps of 2–6 minutes; sent in the creator's local morning (timezone from country, else the founder's); unsubscribe line; stop on bounce.

### 7.6 Claim check (before approval)
- Split the pitch into sentences (code). For each sentence that states something about the creator, ask a Jev Noul: "Is the statement in `sentence` supported by `dossier.evidence`?"
- Any sentence below 0.6 → repair that sentence (LLM) once. If it's still unsupported → flag it in the review queue with the evidence shown.
- Keep the existing rule checks and the Jev style Nouls:
  - `specific_reference` (want high)
  - `template_feel` (want low)
  - `pressure` (want low; skipped for the `offer` variant's fee line)

### 7.7 Follow-ups that feel human (Inngest sequences)
```
sequence_enrollments(enrollment_id, person_id, pitch_id, sequence_id, step_index, status
                     [active, replied, paused, stopped, finished, bounced], next_run_at)
```
Default sequence (editable per campaign):
| Step | When | Channel | Content |
|---|---|---|---|
| 0 | Day 0 | Primary (email) | Approved first message |
| 1 | Day 3–4 | Same thread | Short follow-up written **at send time**: references the creator's newest post if there is one, otherwise adds one new reason |
| 2 | Day 7 | Second platform (assisted DM) | Short note pointing to the email |
| 3 | Day 10–14 | Email | Final, polite close ("happy to circle back later") |

- **Stop on any reply on any platform** (the person model links the threads), on a bounce, or on an opt-out.
- Before each step: a Jev Noul "Does `creator.recent_posts` say they are not taking sponsorships right now?" If above 0.7 → pause, and tell the founder.
- Implementation: one Inngest function per enrollment: `step.sleep_until` → check stop conditions → generate → send → `step.wait_for_event("message/replied", match="data.person_id", timeout=…)`.
- Gmail history poll (Inngest cron) → normalise → emit `message/replied` / `message/bounced`. Follow-ups are drafted when due and wait for approval. Assisted DMs: the founder marks "they replied" in one click.

### 7.8 Review queue: "Needs you" (founder approval UX)
- One queue for outreach and deals: the agent's proposals (send this first message, send this follow-up, reply with this counter, move this deal to Agreed at $X, chase this late post) each with the reason and the evidence. Approve / Edit / Skip; every decision goes into the deal or message log.
- Numbers in a proposal (prices, dates) come from code; Jev reads the creator's message; the LLM only words the message, and code checks the numbers didn't change.
- **Negotiation (Nov 5):** replies and prices are handled by the negotiation agent (§8.7, `app/negotiation/`); the queue only adds time-based nudges (follow-ups, late posts, live, paid). The Nov 4 code formula (40% steps, templates) was removed.
- **Where it lives (Nov 5, replaces the Nov 4 board):** the Deals tab has two views. **Negotiating** is an inbox: creators grouped Your turn / Waiting for them / Agreed / Lost, the conversation as a chat built from `message_sent` and `creator_reply` events, the agent's suggestion as a draft bubble, and a composer to write (`POST /api/deals/{id}/message`, sent from Gmail or recorded as copied; replaces pending suggestions) or paste their reply. **Content** is one row per agreed deal with Agreed → Posted → Paid and one next action. Contacted and Negotiating show as one status. No kanban, no To do list, no bulk approve.
- **The chat (Nov 5, PR 1):** the agent's draft is pre-filled in the message box (label = proposal title, ⓘ = reason; Send approves it with the edited text, ✕ skips it, Reword keeps the terms). A You / creator switch in the box adds pasted replies (`POST /reply`); each side keeps its own unsent text. Messages are optimistic (Sending… → time; failures stay with Retry or Reconnect). Read state: `creator_deals.last_read_at`, set by `POST /api/deals/{id}/read` when the chat opens; `unread` per deal on the list; `GET /api/inbox` (syncs Gmail first, rate-limited per thread) lists chats with unread replies or a pending draft across campaigns for the navbar bell, the tab badge, the "(n)" title and browser notifications (polled every 60 s while open; no push when closed).
- **After agreeing:** a new reply runs the agent in hold mode. A higher ask ("$10 more" → Jev `ask_is_extra`, code adds it to the agreed price) becomes a `hold_terms` proposal (a kind reply keeping the agreed terms) carrying `change: {from, to}`; the deal stays agreed and `quoted_rate` is not touched. `POST /api/proposals/{id}/accept-change` sets the agreed price to their ask instead. Declining after agreeing suggests `mark_lost`.
- **Gmail dedupe:** sync takes a per-deal advisory lock, skips messages already stored, and links a pasted reply with the same text instead of adding the email again; `uq_deal_events_gmail_id` (deal_id, payload->>'gmail_id') backs it up. Pasting text already in the chat returns 409.
- **One Outreach tab (Nov 5, PR 2):** a pitch run (`POST /api/outreach/campaigns/{id}/jobs`) first creates each creator's deal, so the chat exists while the pitch is written ("Writing a first message…", from pending `outreach_pitches`); when the run ends, `drafts_from_job` adds a `pitch` proposal per creator holding the text for each channel (`texts`) and the email subject. Channel per deal (`creator_deals.channel`, else email when we have an address, else the first DM we can open): email sends from Gmail as a new thread with the subject; DMs are recorded as copied and the profile opens. "Send N checked" sends `pitch` drafts the founder has opened (`seen`) by email, one by one, stopping at the Gmail daily cap.
- **Agreeing (Nov 5):** `POST /api/deals/{id}/agree` stores the price and deal type, `pay_when`, the posts (`deal_posts`: deliverable + due date; `post_by` = the earliest), the creator's `tracking_code` (name + 2 digits, unique per campaign) and a `tracking_links` row to the founder's site (remembered as `campaign_details.brand.website`), then drafts a `confirm_terms` message written by code. `/r/<slug>` (Next route) asks the public `GET /api/links/{slug}`, which records a `link_clicks` row unless the user agent looks like a bot or link preview, and redirects to the https target. Track (F7.11) reads these.
- **Track (Nov 5, PR 3):** `refresh_campaign` (daily Inngest `refresh_track`, and on opening Track at most every 30 min) reads each agreed YouTube creator's newest 10 uploads (1 unit), matches planned `deal_posts` by link slug or code in the description, else asks Jev once per upload (`is_sponsored_post` ≥ 0.7); fetches statistics for found posts (1 unit per 50) into `deal_posts` and a daily `post_stats` row; 3 days after live reads up to 60 comments once (Jev: sentiment level, product interest, product questions, ad backlash; top 3 comments by likes kept as written). `report.build` (code only): totals, results by goal kind, cost per result, return when the founder sets a value per result, forecast = Σ views ÷ curve share at the post's age (from day 2, labelled estimate), Rebook/OK/Skip against expected views (typical views × posts) and the median cost per result, To pay (live, or agreed upfront / half). Conversions: `conversions` rows from the snippet (tracking links add `?ref=<code>`; `/t.js` keeps it 30 days in the visitor's localStorage on the founder's site and sends one `sendBeacon` per kind; public `POST /api/t/{key}` with the campaign's public key), store CSV (code → deal) or by hand. Payments: `POST /api/deals/{id}/paid` (amount, date, method, note). `GET /api/campaigns/{id}/track.csv` (formula-safe). Attribution is last link or code, stated in the docs.
- **Track views and setup (Nov 5, PR 4):** three views (Overview, Creators, Posts). Per post (code): `vs_usual` = views ÷ the creator's usual views (trending ≥ 2×, above ≥ 1.2×, below < 0.6× after 3 days), views per day, engagement = (likes + comments) ÷ views against the creator's usual engagement rate, results only when the creator has one live post. Insights (code, each only when backed): late posts, counting not set up, cost per 1,000 views by format (deal cost split evenly over its posts, ≥ 2 live posts per format, ≥ 1.5× apart), cost per result for channels under/over 5k usual views (≥ 1.5× apart), best converter (≥ 3 results), trending post, average price vs fair midpoint (≥ 10% apart). Setup: the snippet sends `{"kind": "ping"}` on `?reachai_test=1` (sets `track.snippet_seen_at`); a backend can POST the same JSON (`ref`, `kind`) to `/api/t/{key}`.
- Built for deals (Nov 4): `agent_proposals(proposal_id, campaign_id, deal_id, key, kind, status[pending|approved|skipped|stale], title, reason, payload, result)`, unique `(deal_id, key)` so an approved or skipped suggestion never returns. Suggestions are recomputed in code whenever the Deals tab loads (`app/agent/proposals.py`, thresholds in `app/agent/constants.py`); approving runs the change from the stored payload through the same checks as a manual edit (`app/deals/changes.py`). Until Gmail is connected, approving a message copies it and records it as sent; a pasted reply is stored as a `creator_reply` event and read by Jev (`declined`, `agrees`, `gives_price` plus the negotiation signals). An edited message keeps its amounts only if it still says exactly our numbers, so "they accepted" can only agree at a price we computed.
- One screen, one card per creator: the pitch, each claim with its evidence chip, contact source + verification status, variant, a send-time preview.
- Actions: **Approve**, **Edit** (the edit is saved to the voice profile), **Skip**. Keyboard shortcuts; target < 10 s per creator.
- "Approve all with no flags" button for creators with zero flags.

### 7.9 Inbox and reply classification
- Page `/campaign/[id]/inbox`: threads grouped by **person** (all channels), with classification chips.
- **Jev reply classifier** (one request per inbound message):
  - `intent` Choice:
    - `interested`
    - `asks_rate_or_details`
    - `sent_rate_card`
    - `counter_offer`
    - `declined`
    - `out_of_office`
    - `wrong_person_or_agency`
    - `question_other`
    - `spam_or_unrelated`

    Each option is an object with `what` / `not_for`.
  - `mentions_price` Noul. If above 0.5: regex finds amounts → Jev picks "Which amount in `candidates` is the creator's quoted price?" → **code** converts currency and compares with `valuation`.
  - `needs_human` Noul ("Does `message.text` raise legal, payment-terms or contract questions?").
- **Routing:**
  - `out_of_office` → reschedule the sequence after the return date (date parts from Jev Choices, comparison in code).
  - `wrong_person_or_agency` → extract the new contact (regex candidates + Jev pick) → ask the founder.
  - Other intents with high confidence → draft a reply (LLM `reply`, with the fair-price range for rate intents) for approval.
  - Low confidence or `needs_human` → "Needs you" tab.

### 7.9b Hardening (Nov 13): checked with simulated models and a stress test
- **Send once:** approving claims the suggestion atomically (`pending → sending`, committed before Gmail is called; `app/agent/queue.claim`). A second click, a second tab or "Send all" at the same time gets 409 and nothing is sent twice; a failed send releases it back to `pending`. A crash between Gmail and the save leaves it in `sending` (never resent automatically).
- **Send all:** each pitch loaded fresh and committed on its own; any error skips that creator and continues; drafts with `needs_review` are never sent in bulk.
- **Pitch checks** (`validate_creator_pitch.py`): money in any currency or "1.5k", links other than the brand's website, email addresses, phone numbers, placeholders, AI/instruction phrases, empty or oversized email/subject/DM; the creator's name matches on its first word (emoji and handles ignored). Still failing after one repair → the draft carries `needs_review` + `problems`. One creator's AI failure → status `failed`, the batch continues.
- **Negotiation:** `numbers_ok` rejects any amount not written as the decided `$` fee; offers are rounded within the ceiling (never up past it); when our last offer exceeds the budget left, no price is suggested; an AI outage stores the reply with a note (`AGENT_DOWN`) and stales the old suggestion. Fuzzed with 6,000+ random Jev answers (`tests/hardening/test_negotiation_fuzz.py`).
- **Gmail sync:** one broken thread is logged and skipped; the bell's sync has a 4 s budget, oldest-checked threads first.
- **Hot paths:** the inbox reads only names and unread previews (creator names via `jsonb_array_elements` in SQL); the Deals page and chat actions read creators cut down to `LEAD_FIELDS` in SQL and load each chat's events once. Stress test: `PERF=1 pytest tests/perf` (10 campaigns × 50 creators, 300 deals).

### 7.10 Assisted DMs (X / Instagram / LinkedIn)
- "Copy and open DM" button: copies the message and opens `x.com/messages/compose?recipient_id=…`, `ig.me/m/<handle>` or the LinkedIn profile. The founder marks it sent in one click → `outreach_messages(channel=dm, status=sent_manual)`.
- No automated cold DMs: they break X's automation rules and put the user's LinkedIn/Instagram account at risk.

### 7.11 Learning what gets replies
- Store per message: variant, angle, prompt version, channel, step, send hour, and creator segment.
- Dashboard:
  - Reply rate and positive-reply rate by variant, angle, channel and step.
  - Time to first reply.
  - Founder edit distance, as a measure of how much the AI got wrong.
- Monthly: feed the most-edited patterns back into the pitch prompt (offline, eval-gated with the existing LangSmith suite).

---

## 8. Phase 7: Deals, posting, tracking, payments

**Decisions:**
- Founder pays creators directly; we send "pay now" requests and track payments.
- Our own short links for clicks.
- Promo codes + a signup snippet / server event for conversions.
- Tracking is included in every plan, Free too (no credits).

**Lifecycle:** `agreed → brief_contract → draft_review (optional) → live → results (day 1–30) → paid → rebook?`

### 8.1 Deal record (everything later is checked against it)
```
creator_deals(deal_id, campaign_id, person_id, stage
              [prospect, contacted, replied, negotiating, agreed, draft_review, live, paid, lost],
              platform, format [dedicated, integration, short, post, story], post_window_start,
              post_window_end, deal_type [flat, base_plus_commission, cpm_capped, affiliate, gifting],
              quoted_rate, agreed_rate, currency, commission_pct, cpm_cap, fair_low, fair_high,
              usage_rights JSONB, exclusivity JSONB, disclosure_required, link_id, promo_code,
              payment_terms [on_live, split_50_50], creator_payment_details JSONB (encrypted),
              tax_ids JSONB (encrypted), contract_url, notes, updated_at)
deal_events(event_id, deal_id, type, payload JSONB, created_at)
```
Stages move automatically from outreach events (sent → contacted, reply → replied) and from the detections below.

**Built (v1, Nov 5):** a simpler first version of this record: `creator_deals(deal_id, campaign_id, creator_id, platform, creator_name, stage [contacted, negotiating, agreed, content, live, paid, lost], position, deliverable [integration, dedicated, short, post, story], post_by, deal_type [flat, base_plus_commission, affiliate, gifted], commission_pct, usage_rights [none, organic, paid_30/60/90], exclusivity_days, disclosure, currency, quoted_rate, agreed_rate, fair_low, fair_high, typical_views (snapshots when added), post_url, live_at, paid_amount, paid_at, payment_ref, notes)` and `deal_events(deal_id, type, payload)`. Stages are moved by the founder for now (board drag-and-drop); automatic moves come with outreach sending (§7) and live detection (§8.3). Person-level deals (`person_id`), usage/exclusivity as JSON, contracts and payment details come later.

### 8.2 Brief, contract, draft review
- The **brief** is generated by the LLM (`reply` route) from the campaign + deal record. The founder edits it.
- **Contract:** a generated simple agreement (deliverables, dates, disclosure, usage rights, payment terms, cancellation, tax ID field) + e-sign (DocuSeal, open source; later).
- **Creator portal:** a magic link, no login: `/c/{token}`.
  - The creator can view the brief, sign, submit a draft (script, file or unlisted link), and later submit the live link and insight screenshots.
  - Tokens are per deal, expire, and are revocable.
- **Draft check:** Jev Nouls over the script or transcript, one per brief requirement:
  - "Does `draft.text` mention `brief.product`?"
  - "…include `brief.key_message`?"
  - "…plan a disclosure?"
  - "…make any claim listed in `brief.forbidden_claims`?"

  The founder approves or requests changes.

### 8.3 Live detection (cheapest reliable first)
1. **Creator submits the post URL** in the portal → validate that the URL belongs to the creator's account (code).
2. **Watcher**, only for `agreed` / `draft_review` deals:
   - Inngest cron every hour for the first 48 h of the posting window, then daily until found or the window passes + 3 days.
   - YouTube `playlistItems` (≈1 unit); X/IG/LinkedIn through the same platform providers (one batched job per run).
   - Stop polling a deal once its post is found.
3. **Match a post to the deal:**
   - Our short-link code or promo code present → **auto-confirm** (exact).
   - Else, brand mentioned (code) **and** Jev Noul "Does `post.text` promote `brief.product`?" > 0.7 → **suggest** a match; the founder confirms in one click. Fuzzy matches are never auto-confirmed.
   - YouTube's paid-promotion flag (`paidProductPlacementDetails`) is readable only by the video owner, so it's not used.
4. **Post checklist** (stored on the deal):

   | Check | How |
   |---|---|
   | `has_link` | Code |
   | `has_code` | Code |
   | `mentions_product` | Jev |
   | `posted_in_window` | Code |
   | `disclosure` | Code checks for labels, then Jev reads the description/transcript |
   | `still_live_d7`, `still_live_d30` | Code re-check |

   For `disclosure`:
   - Code looks for #ad, #collab, #promo, #sponsored, #partnership (ASCI), plus "paid partnership" or "sponsored".
   - Then a Jev Noul on the description/transcript: "Does `post` clearly tell viewers it is paid or sponsored?"
   - We recommend "#ad" in briefs, since one source says #collab alone may not satisfy ASCI's 2026 update (unverified).
5. **Alerts** in the "Needs you" panel: posted, missing link/code, no disclosure, deadline passed, post deleted.

### 8.4 Results tracking
```
post_snapshots(snapshot_id, deal_id, captured_at, views, likes, comments, shares, source)
tracking_links(link_id, deal_id, slug, destination, created_at)
link_clicks(click_id, link_id, ts, ip_hash, ua_hash, country, referrer, is_bot)
conversions(conversion_id, deal_id, link_id, type [signup, purchase], value, currency,
            source [snippet, server_event, promo_code], external_id, ts)
```
- **Snapshots** at day 1, 3, 7, 14, 30 after live (Inngest scheduled steps). Few posts per campaign, so the cost is very low.
- **Instagram Stories:** they expire in 24 h, so the creator uploads an insights screenshot in the portal. An LLM with vision (`brief` route or a vision-capable route) reads the numbers; code checks they're plausible (e.g. views ≤ followers × 3); the founder sees "creator-reported".
- **Clicks, using our own short links:**
  - `GET /r/{slug}` → log the click → `302` to the destination with UTM params (`utm_source=reachai&utm_medium=creator&utm_campaign={campaign}&utm_content={slug}`) + `rid={click_id}`.
  - Bot filter: known bot user agents, prefetchers, and repeat clicks from the same `ip_hash` within 30 s.
  - The IP is hashed, never stored raw.
  - Later: a custom domain per user (e.g. `go.theirbrand.com`).
- **Conversions:**
  - **Promo codes:** a unique code per deal. Redemptions arrive through the server event below, or are entered by the founder.
  - **Signup snippet:** `<script src="…/rt.js" data-key="…">`. It stores `rid` from the landing URL in a first-party cookie (30 days), and the founder calls `reachai.track('signup')` on their signup success.
  - **Server event:** `POST /v1/conversions` with an API key: `{rid | promo_code, type, value, currency, external_id}`. Deduplicated on `external_id`.
  - Stripe/Shopify connect: later.
- **Computed metrics (code):**
  - Actual CPM = fee / views × 1000; CPC = fee / clicks; cost per signup; ROI = revenue / fee.
  - **Forecast vs. actual** (views, clicks).
  - Earned media value shown as a secondary number only.
- Results feed the learning loop (§9): `agreed_rate` + outcomes → the pricing model; beat/miss forecast → the ranker.

### 8.5 Results UI
- **Campaign → Results tab:**
  1. **Summary row:** spent, posts live (x of y), views, clicks, signups, cost per signup, each with its forecast.
  2. **One row per creator:** stage pill, checklist icons, view-curve sparkline, clicks, signups, "×-forecast" badge.
  3. **Creator detail:** timeline of `deal_events`, post preview, contract, payment status.
  4. **"Needs you" panel:** alerts from §8.3 + payment due.
  5. **"Rebook" list:** creators above forecast.
  6. Later: a shareable read-only report link.
- **Pipeline board** `/campaign/[id]/pipeline`: drag-and-drop across stages.

### 8.6 Paying creators (decided: founder pays, we track)
- No funds pass through ReachAI, so no payment-aggregator or escrow licence is needed.
- **Payment request:** when a deal's terms are met (`on_live`: post confirmed and checklist passed; `split_50_50`: on signing + on live), the founder gets a "Pay $X to {creator}" card with the creator's payment details (from the portal: bank/UPI/PayPal/Wise email) and the due date.
- "Mark paid" (with optional reference or receipt upload) → `stage=paid` → a "Paid" receipt is shown to the creator in the portal.
- Reminders: the due date, then +3 days and +7 days.
- **Tax reminders (not advice):**
  - India: TDS on cash fees (commonly 10%); TDS on gifted products worth more than ₹20,000 a year (10%, previously §194R; reportedly moved to the Income Tax Act 2025 from Apr 2026, unverified).
  - US: a 1099 above the IRS threshold (verify).
  - Tax IDs (PAN / W-9) are collected in the contract step and encrypted at rest.
- **Later (option, not now):** payments through a licensed payout partner (money held until verified, then paid out) for a ~3–5% fee, once volume justifies it.

### 8.6b Negotiation agent (built Nov 5, roadmap F7.9)
LangGraph graph in `app/negotiation/graph.py`, run whenever a creator's message arrives (Gmail sync, or pasted/typed by the founder):

```
judge (one Jev request) → guard (code) → write (LLM route "reply") → check (code + Jev) → [rewrite once] → suggestion
```
- **Context (code, free):** creator (views, steadiness, engagement, recent sponsored posts and sponsor brands, country), goal, product, deliverable, usage, fair range, budget and what's not yet committed, anonymous agreed prices for similar-size creators on ReachAI (shown only with ≥ 5 deals), round, our last offer, their previous ask, and the last 12 messages both ways.
- **Jev reads:** `their_fee` / `their_commission` as Choices among the amounts code found in their message (so "7 + 20% commission" is $7 + 20%); `declined`, `agrees`, `firm`, `flexible`, `wants_commission`, `asks_question`, `injection` (Nouls).
- **Jev decides:** `move` (accept, counter, restructure, hold, walk away), `structure` (flat, fee + commission, commission only, smaller scope), `commission` (0–25% in 5% steps), `concession` (Score, 5 levels), `extra` (repeat posts, free product, fast payment). Options live in `app/judge/constants.py`.
- **Code guards** (`app/negotiation/decide.py`): ceiling = min(fair top × 1.15, budget left); opening fee halfway between the bottom and middle of the fair range; later rounds move `concession share` × (their ask − our last fee) and never below our last fee; commission takes 1.5% off the fee per point; accept only within the ceiling; reaching their ask becomes an agreement; final offer at the ceiling or after 4 rounds; injection → no suggestion, the founder reads it.
- **Writer:** sees TERMS, the facts, the conversation and the creator's latest message as data; must use only the decided amounts. **Checks:** code allows only the decided fee and % (fee required); Jev flags extra promises. Fail → rewrite once with the reason → else a short standard message.
- **Result:** one pending suggestion per deal (`agent_proposals.key = nego:<reply event>`, older ones marked stale) with the reasons in plain words; the reply event keeps `their_ask` and the agent's action; the deal's `quoted_rate` / `quoted_commission_pct` update.

### 8.7 Pricing a creator (fair range + deal design)
- **Fair range** `fair_low…fair_high` (P25–P75):
  - From now on: median views × platform CPM prior (by industry and geo), with the spread from view volatility.
  - LinkedIn (no public views): a transacted-price prior by follower tier.
  - Later: the regression in §9.
- **Add-ons** (config in `deals/pricing_constants.py`, market priors from vendor blogs, to be tuned):

  | Add-on | Uplift |
  |---|---|
  | Paid-ads usage 30–90 days | +30–50% |
  | Full buyout | +100–150% |
  | Exclusivity | +20–30% |
  | Dedicated vs. integration | Separate base |

- **Deal type suggestion** by campaign goal:

  | Goal | Deal type |
  |---|---|
  | Awareness | Flat |
  | Signups/sales | Base + 5–20% commission |
  | Proven reach | CPM-capped |
  | Small creators | Affiliate / gifting |

- **Negotiation helper (built):** the fair range is first adjusted for the deal (format multiplier × (1 + usage uplift + exclusivity uplift), `app/deals/constants.py`). Quote vs. that range → `great` (< low), `accept` (≤ high), `counter` (> high: counter at the midpoint, reason from typical views), `walk_away` (> 2 × high: offer the top at most).
- **Reply (built):** code writes an instant template from those numbers. If the founder pastes the creator's reply, one Jev request (`creator_reply_questions`: open to negotiate, firm price, wants commission, mentions usage, injection) picks the angle in code: `budget`, `performance` (base 70% of the counter + 10% commission; also the default for signup/sales goals) or `scope`. "Rewrite with AI" uses LLM route `counter` (Groq gpt-oss-120b, then Gemini Flash-Lite) with the numbers and angle only, never the creator's text; code rejects any wording whose money figures or percentages differ from ours and falls back to the template.
- **Budget planner** (code):
  - Input: total budget, goal metric, candidate creators with fair ranges and forecasts.
  - Choose the set that maximises expected clicks (or signups) within budget: 0/1 knapsack with ≤ 50 items, using an exact DP on budget buckets of $10.
  - Output: "With $3,000: these 5 creators, ~2,100 expected clicks."

### 8.8 Error checks and cost controls
- Only watch agreed deals, more often inside the window, and stop when found.
- The creator-submitted link comes first; automatic detection is the backup.
- Only exact link/code matches are auto-confirmed.
- Bot-click filter; conversions deduplicated by `external_id`.
- Snapshots on a fixed schedule, not continuous polling.
- Payment details and tax IDs encrypted; the portal tokens are scoped to one deal.

---

## 9. The learning loop (long-term advantage)
Every campaign produces labels we can learn from:

| Signal | Label |
|---|---|
| User saves a lead | Positive (weak) |
| User excludes / ignores a top-10 lead | Negative (weak) |
| Creator replies `interested` | Positive (medium) |
| Deal `agreed` | Positive (strong) + **real price** |
| Deal `live` with clicks | Outcome (strongest) |

- **Ranker:** after about 300 campaigns with saves, or 100 deals, train LightGBM LambdaRank on metrics + Jev probabilities. A/B test it against the formula score in §4.7.
- **Valuation model:** a regression of `agreed_rate` on followers, median views, ER, niche, platform and country. Replaces the static CPM tables when its error beats the table on held-out deals.
- Store every Jev answer (`creator_judgments`) so models can be retrained without re-calling Jev.

---

## 10. API surface (new / changed)
```
GET  /platforms                                   → enabled platforms + credit cost per run
POST /campaigns/{id}/estimate                     → {credits, breakdown}
POST /campaigns/{id}/run                          (existing trigger; now reserves credits)
GET  /creators/{creator_id}                       → profile + latest snapshot + judgments
GET  /campaigns/{id}/skipped                       → {looked_at, skipped, reasons[{reason, count}]} (built)
GET/POST /campaigns/{id}/shares, PATCH/DELETE /shares/{link_id} → owner manages view-only links (built)
GET  /share/{token}                               → public, allowlisted shortlist; 404 unknown, 410 off/expired (built)
PUT  /share/{token}/feedback/{creator_id}          → reviewer verdict + comment (built)
GET  /campaigns/{id}/feedback                      → owner: what reviewers said (built)
GET  /campaigns/{id}/share-activity                → owner: people, events (opened/feedback), by creator (built)
GET/POST /campaigns/{id}/deals, PATCH/DELETE /deals/{deal_id}, GET /deals/{deal_id}/events → deals board (built)
POST /deals/{deal_id}/counter {creator_reply?, rewrite?}       → advice + reply message (built)
POST /campaigns/{id}/creators/{cid}/contact       → find + verify email (1 credit)
POST /connections/inbox/start | GET /connections  → Google OAuth link (Gmail), list
POST /outreach/jobs/{job_id}/send                 → enroll selected pitches into a sequence
POST /outreach/pitches/{pitch_id}/mark-sent       → assisted DM
GET  /campaigns/{id}/inbox | GET /threads/{tid}   → threads + classification
POST /threads/{tid}/reply                         → send approved draft
GET/PATCH /campaigns/{id}/deals, /deals/{deal_id}
GET  /billing | POST /billing/checkout | POST /billing/topup | GET /billing/ledger
POST /api/webhooks/dodo | POST /webhooks/unipile
```

---

## 11. Instrumentation, evaluation, observability
Since validation was skipped, these are **required** from Phase 1:
- **Product events** (table `product_events` or PostHog):
  - run_started / run_completed (platform, credits, duration)
  - lead_saved / lead_excluded
  - contact_found, pitch_generated, pitch_edited (edit distance), message_sent
  - reply_received (intent), deal_stage_changed
  - checkout_started / paid
- **Dashboards:**
  - Runs per platform
  - Save rate in the top 10
  - Contact find rate
  - Reply rate
  - Cost per run vs. credits charged (margin)
  - Activation (free run → paid)
- **LangSmith:** trace every graph run. Keep the outreach eval suite; add a discovery eval (precision of the top 10 against labelled creators).
- **Jev monitoring:** `response.model`, tokens, latency, fallback rate. A weekly sample of 20 judgments checked by a human.

---

## 12. Compliance checklist
- [ ] YouTube API data refreshed or deleted after 30 days (§4.4). Confirm the current policy text.
- [ ] X: third-party provider terms; switch to the official API is ready (`X_PROVIDER`).
- [ ] LinkedIn: logged-out public data only; no fake or logged-in accounts.
- [ ] Instagram: Apify public data only.
- [ ] Email: unsubscribe line, honour opt-outs globally (`suppression_list` table), send only to verified business contacts.
- [ ] Personal data (GDPR / India DPDP Act): privacy policy, deletion on request, data retention job.
- [ ] Jev: creator text is untrusted (separate state fields + `injection` Noul); no Jev answer alone triggers a send or payment.
- [ ] Dodo Payments is merchant of record and files sales tax abroad; a CA confirms our GST treatment (LUT) and income tax before live payments.
- [ ] YouTube: terms link YouTube's Terms of Service, privacy links Google's Privacy Policy, quota-increase audit submitted (`docs/plans/youtube-quota.md`).

---

## 13. Delivery plan
| Phase | Contents | Depends on | Size (rough) |
|---|---|---|---|
| 0 | LLM gateway wrapper + routes, Jev client, config, cost logging | — | S |
| 1 | `CreatorProfile`, person model, creator DB (pgvector) + caches + YouTube 30-day job, discovery ladder + streaming, adapters base, generic graph, metrics + anomaly, Jev judge + scoring, YouTube migrated, UI badges | 0 | L |
| 2 | Credits ledger, reservations, plans, Dodo Payments subscriptions/packs/webhooks, billing UI | 0 | M |
| 3 | X adapter | 1, 2 | M |
| 4 | Instagram adapter | 1, 2 | M |
| 5 | LinkedIn adapter (public post search + pasted URLs) | 1, 2 | M |
| 6 | Contacts + verification, Gmail inbox (Google OAuth), sequences, inbox UI, reply classifier, assisted DMs, pitch validation upgrade | 1, 2 | L |
| 7 | Deal record, creator portal, draft review, live detection + checklist, snapshots, short links, conversions (promo codes, snippet, server event), results UI, pay-on-proof requests, fair range + budget planner | 6 | L |
| 7b | Extra sources: lookalikes, competitor sponsors (with Phase 3), founder followers (with X), pre-warmed niches (after usage) | 1, 3 | M |
| 8 | Learned ranker + valuation model | data from 6–7 | M |

Phases 3 and 6 can run in parallel after 1 and 2.

### File change map (first phases)
| File | Change |
|---|---|
| `backend/app/core/model.py` | Removed Nov 4 (K2): outreach and the eval judge use `app/llm` routes `pitch` and `judge_eval` |
| `backend/app/my_agent/**` | Removed Nov 4 (F1.13): logic lives in `app/discovery/` + `app/platforms/youtube.py` + `app/metrics/` |
| `backend/app/workflow/runtime.py`, `app/inngest/functions.py` | Run the generic graph; stage list from the graph; credit reserve/commit |
| `backend/app/outreach/nodes/validate_creator_pitch.py` | + Jev Nouls (§7.6) |
| `backend/app/outreach/utils.py` | `available_channels` / evidence read `CreatorProfile` |
| `backend/app/models/*` + `alembic/versions/*` | New tables (§4.4, §5.2, §7, §8) |
| `backend/app/models/transaction.py`, `users.credits` | Superseded by `credit_ledger` (migration converts the balance) |
| `frontend/components/MultiPlatform.tsx` | Platforms from `/platforms` |
| `frontend/app/ListOfInfluencer/*` | Badges, score breakdown, Jev answers |
| `frontend/components/OutreachDialog.tsx`, `app/campaign/[id]/outreach/*` | Send / sequence controls, assisted DM |
| New: `frontend/app/campaign/[id]/inbox`, `/pipeline`, `frontend/app/billing` | New pages |
| `README.md` | Rewrite after Phase 1 |

---

## 14. Risks and open items
| Risk / unknown | Mitigation |
|---|---|
| LangSmith Gateway is beta; fallback chains only accept OpenAI-compatible endpoints; bring-your-own-key pricing unconfirmed | Wrapper + `LLM_BACKEND` switch (OpenRouter / direct) |
| Jev is new (launched Sept 2026); calibration isn't reliable out of the box | Labelled set, pinned version, LLM fallback route |
| Third-party X / Apify actors change or break | Provider abstraction, fixture tests, fallback actor per platform, alerts on result counts |
| YouTube quota (~10 runs/day) | Quota extension request; cache; video search with time filters |
| Data costs are higher than estimated | `cost_events` → adjust credits per action monthly; hard caps per run |
| Building for two segments (B2B + consumer) without validation | Instrumentation (§11); review platform usage after the first 50 paying users |
| Email deliverability on user inboxes | Caps, verification, bounce stop, unsubscribe |
| Prices quoted in this spec come from third-party sources | Confirm with each vendor before launch (Dodo Payments, Apify, X provider, gateway, verifier) |

---

## 15. Agent access over MCP

**Goal:** a founder drives ReachAI from their own agent (Claude, ChatGPT, Cursor, Claude Code, Codex, VS Code) and everything they do shows up in the web app, because it is the same database.

**Why not a "do everything" tool:** the user's agent already plans. Typed tools let it chain steps, keep our cost near zero, and make results predictable. Our own LLM is not called on the MCP path unless the user asks for it (`generate_pitches`).

### 15.1 Server
- Official Python `mcp` SDK (`MCPServer`), stateless, JSON responses, mounted inside the FastAPI app at `/api/mcp` (Vercel already routes `/api/*` to the backend).
- The HTTP app is built per request (no dependency on ASGI lifespan, which serverless hosts may not run). Tool definitions are built once.
- Protected-resource metadata is served at `/.well-known/oauth-protected-resource/api/mcp` (RFC 9728); `vercel.json` rewrites that path to the backend.
- Host/Origin allow-list comes from `MCP_PUBLIC_URL` (+ localhost). DNS-rebinding protection stays on.

### 15.2 Auth (decided: Clerk OAuth + personal API keys)
- **Clerk OAuth** (Clerk is the authorization server; CIMD for client registration). The server verifies `oat_` access tokens with Clerk's backend API (`CLERK_SECRET_KEY`), reads the user from `subject`, and maps it to our `users` row like `get_db_user`. If the verified payload carries an audience, it must include `MCP_PUBLIC_URL`.
- **Personal API keys** (`rai_...`) for agents that cannot do OAuth. Created in the app, shown once, stored as SHA-256 only (`api_keys`: prefix, hash, name, last_used_at, revoked_at). Revocable.
- Every tool runs as that user and only touches that user's rows.

### 15.3 Tools (v1, read-mostly)
`list_campaigns`, `get_campaign`, `campaign_status`, `list_creators`, `get_creator`, `list_saved`, `save_creator`, `unsave_creator`. Annotations mark read-only vs. writing tools. Creator text (names, bios, descriptions) is returned inside a field named `untrusted` and never mixed into instructions (architecture rule 7).

### 15.4 Presentation
- Each tool returns a markdown block (tables, a one-line metrics summary, a link to the web app) **and** `structuredContent`. Formatting lives in one module (`app/mcp/format.py`).
- Server `instructions` carry the short presentation rules (tables for creators, numbers exactly as returned, never recompute prices). The longer playbook goes in the skill (F9.2). Only Claude Code and Codex load skills, so the short rules must live in the server.
- Numbers come from our code. The agent arranges what we return; it does not calculate.

### 15.5 Write tools (F9.2, built) and later
- `create_campaign` saves a brief in the same shape as the web form and does not start anything. `start_search` queues the run through the shared `app/api/campaign_runs.start_run` (also used by the web route). It spends YouTube quota and Jev calls, so it needs `confirm=true` (the first call only previews), refuses a campaign that is already running, and is capped per user per day (`MCP_RUNS_PER_DAY`, default 10 since Nov 13 (was 3; credits now limit spend), counted in `agent_runs`).
- `pitch_context` returns the brand, the creator's numbers, the fair range, the best channel and the rules; creator text is under `untrusted`. `save_draft` checks the agent's text in code (`app/mcp/drafts.py`: no price above the creator's fair-high, none at all when there is no fair price, no placeholders, internal terms or package details, brand and creator named, at most 2 questions and 2 links) and saves it as an `AgentProposal` of kind `pitch`, key `pitch:agent`, payload source `agent`, in the creator's chat. It adds the creator to Outreach if needed, replaces its own pending draft, and refuses once a message was sent or the draft was handled. Nothing is sent.
- Read tools: `inbox` (unread replies and drafts waiting; never syncs Gmail), `list_deals`, `track_summary` (uses the same builders as the Track tab but does not create the signup key). Prompts: `reachai-new-campaign`, `reachai-draft-pitches`, `reachai-check-inbox`.
- Not built: reply drafts (replies stay with the negotiation agent, whose amounts are checked by code), and sending, agreeing terms and marking paid (F9.5): these always need the founder's confirmation in the web app; nothing an agent says triggers them. F9.5 can build on the Outreach chat now that Gmail (F6.5) and Deals (F7.1) shipped.

### 15.6 MCP Apps (F9.3)
Interactive creators table and campaign summary through the MCP Apps extension. Verified (Nov 2026, official docs) as supported in Claude (web, desktop, iOS) and VS Code Copilot; ChatGPT, Cursor and Codex not confirmed, so every tool keeps its markdown fallback. Keep tool results under ~150,000 characters (claude.ai) / 25,000 tokens (Claude Code); paginate.

### 15.7 Distribution
`/llms.txt` + `/skill.md` (built, served by the backend from `MCP_PUBLIC_URL` only, never from request headers) + a docs page with the one-line add command per client. Directory listings (Claude, ChatGPT) after the OAuth flow is proven in a custom connector.

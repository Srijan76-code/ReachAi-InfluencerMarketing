# How ReachAI chooses its AI models and prompts

Every model and prompt ReachAI uses was picked with a live test, not from leaderboards. Leaderboards disagree,
none of them measures our tasks, and a model's speed and reliability change month to month. This page records
each test, its results and the decision it led to. **Rerun the scripts in `backend/scripts/benchmarks/` before
changing a model or a prompt**, and add the new results here.

How every test works:

- the same real task for every model, several runs each;
- **code** checks the exact rules (word counts, prices that must match, placeholders like "[Your Name]");
- **Jev** scores what needs judgment (did it invent anything, does it sound like a person, does it agree with
  our verdict);
- we compare failures, speed, cost per call and quality, then pick a main model plus backups from **other
  providers**, so one company's outage never stops ReachAI.

## Where AI models are used

| Part of ReachAI | Task | Route | Needs |
|---|---|---|---|
| Lead generation | Search strategy (keywords, topics, competitors) | `strategy` | Judgment: everything downstream depends on it |
| Lead generation | "Why this creator" bullets | `reasons` | Only correctness: no tone, nothing new |
| Outreach | First messages (pitches) | `pitch` | Natural writing, no invented facts |
| Outreach | Replies, follow-ups, counter-offers | `reply` | Natural writing, exact prices, no invented facts |
| Both | Backup judge when Jev is down | `fit_fallback` | Fast and cheap |

The order of models for each route lives in `backend/app/llm/routes.py`.

## How models are reached (Nov 15)

**Vercel AI Gateway** for Claude and GPT: one key, no markup on tokens, $5 free credit a month. Gemini (Google
key) and gpt-oss (Groq key) are called directly as backups, so ReachAI still answers if the gateway is down.
The fallback logic is our own (`app/llm/client.py`), so it costs nothing.

| Option | Markup | Why not chosen |
|---|---|---|
| Vercel AI Gateway | 0% | **Chosen** |
| OpenRouter | 5.5% on credit purchases | Costs more for the same models |
| Cloudflare AI Gateway | 0% | Needs a separate account with every AI company |
| LangSmith LLM Gateway | Not stated | Beta; no OpenRouter or Groq; needs a key per company |

A Claude Pro subscription doesn't include API use (only Max and Team plans get monthly API credit).

---

## Outreach: which model writes replies (Nov 15)

**Task:** the founder's reply to a creator who asked $320 and asked about ad usage rights. Make a counter-offer
of $195 + 10% commission, and say usage rights aren't decided. 8 runs per model, through OpenRouter.

| Model | Worked | Typical time | Cost per reply | Invented something (Jev) | Sounds like a founder (Jev, 0–3) |
|---|---|---|---|---|---|
| Claude Sonnet 5.5 | 8/8 | 3.6 s | $0.0045 | 0/8 | **2.39** |
| **Claude Haiku 5.5** | 8/8 | 2.8 s | **$0.0003** | **0/8** | **2.30** |
| GPT-5 mini | 8/8 | 4.1 s | $0.0005 | 0/8 | 2.16 |
| Claude Haiku 4.5 | 8/8 | **1.3 s** | $0.0007 | 3/8 (promised things) | 2.08 |
| gpt-oss-120b | 8/8 | 1.8 s (slowest 8.2 s) | $0.0002 | 0/8 | 1.78 |
| GPT-5.4 mini | 8/8 | 2.8 s | $0.0008 | 0/8 | 1.59 |
| GPT-5.6 Luna | 8/8 | 1.5 s | **$0.0001** | 0/8 | 1.43 |
| Gemini 3.5 Flash | 3/8 | 5.8 s | $0.0084 | 0/3 | 0.84 (cut off) |
| Gemini 3.1 Flash-Lite | 2/8 | 1.2 s | $0.0002 | 1/2 | 2.22 |

**Direct calls to Google and Groq** (same task, 5 runs each):

| Model | Worked | Typical time | Notes |
|---|---|---|---|
| Gemini 3.5 Flash | 5/5 | 3.7 s | Best of the direct models |
| Gemini 3.1 Flash-Lite | 5/5 | 0.9 s | Invented "worked well for our partners" |
| gpt-oss-120b (Groq) | 5/5 | 0.8 s | Stiff; left "[Your Name]" |
| **Gemini 3.8 Flash** | **0/5** | — | Timeouts and "overloaded" errors (was ReachAI's main model) |
| Gemini Pro latest / 3.1 Pro | 0/5 | — | Our Google key has no quota for Pro |

**Decision:** Claude Haiku 5.5 writes, then GPT-5 mini, then Gemini 3.5 Flash (direct), then gpt-oss (Groq).
Gemini 3.8 Flash was removed everywhere. GPT-5 mini runs with low reasoning effort (14 s → 8 s on a structured
reply). Every model invented something at least once in other tests, which is why the reply agent (being built)
has Jev check every sentence of every reply before it's sent.

Script: `outreach_reply_models.py`, `direct_providers.py`.

---

## Lead generation: which model writes "Why this creator" (Nov 15)

**Task:** the "why this creator" text for 3 creators (strong fit, weak fit, one to avoid), 3 runs each, with
the prompt then in the code.

| Model | Worked | Typical time | Cost | Followed the rules | Agreed with the verdict | Invented something (Jev) |
|---|---|---|---|---|---|---|
| **Claude Haiku 5.5** | 9/9 | 2.4 s | $0.0002 | 9/9 | 9/9 | **2/9** |
| Gemini 3.5 Flash-Lite | 8/9 | **0.9 s** | $0.0001 | 8/8 | 8/8 | 4/8 |
| GPT-5 mini | 9/9 | 4.5 s | $0.0005 | 9/9 | 9/9 | 7/9 |
| GPT-5.6 Luna | 9/9 | 1.5 s | $0.0001 | 9/9 | 9/9 | 7/9 |
| Gemini 3.1 Flash-Lite | 9/9 | 1.0 s | $0.0001 | 9/9 | 9/9 | 7/9 |
| gpt-oss-120b | 9/9 | 1.7 s | $0.0001 | 9/9 | 9/9 | 8/9 |
| Claude Haiku 4.5 | 3/9 | 1.1 s | $0.0004 | 3/3 | 3/3 | 3/3 |

"Invented" here means claiming more than the data shows ("his fans care about workouts, not structured morning
habits"). **Decision:** Claude Haiku 5.5 with thinking off, then Gemini 3.5 Flash-Lite, then gpt-oss.

Script: `reason_models.py`.

## Lead generation: which prompt for "Why this creator" (Nov 15)

The text became **3 bullets: why them · watch out (or another strength) · when to choose them**, one plain
sentence each. Tested on Claude Haiku 5.5 with 6 creators (strong fit, weak fit, avoid, rising with an unclear
country, unusual engagement, promoted a competitor), 3 runs each.

| Prompt | Format right | Bullets with something unsupported | Bullets with two points | Agreed with verdict | Useful (Jev, 0–3) |
|---|---|---|---|---|---|
| A: all data, the model decides what to say | 2/18 | 2/54 | 2 | 12/18 | 0.42 (often empty or cut off) |
| B: code picks up to 3 facts per bullet | 13/18 | 7/54 | 14 | 17/18 | 1.52 |
| C: B + an example | 9/18 | 6/54 | 10 | 14/18 | 1.12 |
| D: B, rewritten tersely | 17/18 | 8/54 | 25 | 18/18 | 1.94 |
| E: **one fact per bullet** | 18/18 | 6/54 | 12 | 18/18 | 2.15 |
| F: E + one of their post titles as proof | 5/18 | 11/54 | 14 | 18/18 | 2.16 |
| **G: F + one example** | 17/18 | **3/54** | **3** | 18/18 | 1.91 |
| H: G with "and they post …" in the example | 18/18 | 8/54 | 16 | 18/18 | 1.92 |

Lessons: give each bullet one fact (several facts get crammed into one sentence); one example fixes the format;
the example's wording is copied, so it must say "they", never "he" or "she".

**Decision: prompt G**, inside this loop (`app/discovery/reason_points.py`, `reason_check.py`):

1. **Code lists the true facts** from Jev's earlier answers and our badges: every reason they fit, every
   weakness, every extra strength, their recent titles. Nothing is inferred.
2. **Jev picks** what matters for this brief: the strongest reason, the title that best shows the fit, the
   weakness that matters most.
3. **Claude Haiku 5.5 words them** (prompt G).
4. **Jev checks** the bullets. Critical problems: a bullet says something not in the facts, the bullets
   contradict the verdict, or the watch-out bullet is the wrong kind; code also catches "he/she" (an exact word
   check). Critical → the model gets the facts, its last bullets, what was right and what to fix, at most twice.
   Minor problems (two points in one bullet) pass.
5. Still wrong, or Jev or every model is down → the facts themselves are shown. Never wrong, just plainer.

| Version of the loop (18 live runs) | Passed first try | After a rewrite | Fell back to facts | Notes |
|---|---|---|---|---|
| 1: first version | 18 | 0 | 0 | Guessed pronouns ("her viewers"); used a title as proof of who watches |
| 2: + Jev checks for those two | 0 | 1 | 17 | Those two Jev questions were too convoluted and rejected good bullets |
| **3: final** | **18** | 0 | 0 | Titles only back up content reasons (in code); pronouns caught in code; 1.2 s each |

Jev picked a better proof title than the word-match code in 8 of 18 runs ("How I track 6 habits" over "My 5AM
morning routine" for a habit app).

Scripts: `reason_prompts.py`, `reason_loop.py`.

---

## Still to test

- **Search strategy** (`strategy`): judgment matters more than price there, and it's one call per search.
  Compare Claude Haiku 5.5 and GPT-5 mini on the queries they produce.
- **The reply agent** with simulated creators (pushy, off-topic, legal questions, out of office) once it's
  built: how often it invents, crosses a limit, or misses a question.

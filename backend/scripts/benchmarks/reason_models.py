import asyncio, os, re, sys, time, statistics, json, httpx, logging
logging.disable(logging.CRITICAL)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from typesafe_sdk import Noul
from app.judge.client import judge
from app.discovery.brief import parse_brief
from app.discovery.prompts import reason_prompt

brief = parse_brief({"brand": {"name": "Lumen", "core_outcome": "a habit-tracking app that helps busy professionals build morning routines", "industry": "productivity", "business_model": "b2c"},
                     "audience": {"target_persona": "busy young professionals who want better habits"}, "campaign": {"goal": "signups"}})
CREATORS = [
  ("Priya Builds", ["My 5AM morning routine that changed my life", "How I track 6 habits without burning out", "Notion vs paper planner for habits", "What I eat in a day as a software engineer", "Atomic Habits: 3 ideas I actually use"],
   {"audience": "young professionals", "covers pain points": "yes, habit consistency", "topic fit": "strong"}, "Strong Buy"),
  ("GymBro Kev", ["Chest day PR attempt", "Best protein powders ranked", "Morning workout routine for beginners", "Bulking diet full day", "Gym fails compilation"],
   {"audience": "fitness enthusiasts, mostly students", "covers pain points": "partly, routines but only workouts", "topic fit": "weak"}, "Consider"),
  ("The Money Desk", ["Index funds explained", "How I budget my salary", "5 side hustles for 2026", "Credit score myths", "My morning routine as a finance YouTuber"],
   {"audience": "young professionals", "covers pain points": "no, mostly money topics", "topic fit": "weak"}, "Avoid"),
]
MODELS = ["anthropic/claude-haiku-5.5", "openai/gpt-5-mini", "openai/gpt-5.6-luna", "google/gemini-3.5-flash-lite", "google/gemini-3.1-flash-lite", "openai/gpt-oss-120b", "anthropic/claude-haiku-4.5"]
RUNS = 3
Q = {
  "invented": Noul(instructions="Does `sentence` claim anything about the creator or their audience that is not supported by `recent_videos` or `what_we_know`?"),
  "agrees": Noul(instructions="Does `sentence` agree with `verdict` (it doesn't call a weaker fit strong, or a strong fit weak)?"),
}
async def call(c, m, prompt):
    body = {"model": m, "messages": [{"role": "user", "content": prompt + "\n\nReply with the sentence only."}], "max_tokens": 1500}
    if m.startswith("openai/gpt-5"): body["reasoning"] = {"effort": "low"}
    r = await c.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": "Bearer dummy"}, json=body, timeout=90)
    r.raise_for_status(); j = r.json()
    return (j["choices"][0]["message"].get("content") or "").strip().strip('"'), j.get("usage", {})
async def one(c, m, cr):
    name, titles, sig, verdict = cr
    prompt = reason_prompt(brief, name, titles, sig, verdict)
    t0 = time.monotonic()
    try:
        text, usage = await call(c, m, prompt)
        if not text: raise ValueError("empty")
    except Exception as e:
        return {"error": f"{type(e).__name__}:{getattr(getattr(e,'response',None),'status_code','')}"}
    dt = time.monotonic() - t0
    j = await judge({"recent_videos": titles, "what_we_know": sig, "verdict": verdict, "sentence": text}, Q, allow_fallback=False)
    words = len(text.split())
    return {"s": dt, "cost": float(usage.get("cost") or 0), "text": text, "creator": name,
            "rules_ok": ("Lumen" in text) and 12 <= words <= 30 and not re.search(r"\d", text),
            "invented": j.noul("invented"), "agrees": j.noul("agrees")}
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS, exist_ok=True)

async def main():
    res = {}
    async with httpx.AsyncClient() as c:
        for m in MODELS:
            runs = await asyncio.gather(*(one(c, m, cr) for cr in CREATORS for _ in range(RUNS)))
            ok = [r for r in runs if "error" not in r]; res[m] = runs
            if not ok:
                print(m, "all failed", [r['error'] for r in runs]); continue
            n = len(runs)
            print(f"{m:30s} ok {len(ok)}/{n} med {statistics.median(r['s'] for r in ok):.1f}s max {max(r['s'] for r in ok):.1f}s "
                  f"cost ${statistics.mean(r['cost'] for r in ok):.5f} rules_ok {sum(r['rules_ok'] for r in ok)}/{len(ok)} "
                  f"invented {sum(r['invented']>0.5 for r in ok)} agrees {sum(r['agrees']>0.5 for r in ok)}/{len(ok)}", flush=True)
    json.dump(res, open(os.path.join(RESULTS, "reason_models.json"), "w"), indent=1)
asyncio.run(main())

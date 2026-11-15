import asyncio, os, re, sys, time, statistics, json, httpx
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from typesafe_sdk import Noul, Score
from app.judge.client import judge

SYSTEM = ("You write the next email from a startup founder to a content creator, as the founder. Plain text, no subject, "
          "40-120 words, warm and specific, no cliches. Use ONLY the facts given; never invent anything (no claims about "
          "the company, past partners or decisions). Sign off with the founder's first name: Maya.")
FACTS = ("Brand: Lumen, a habit-tracking app. Goal: app signups. Creator: Priya (morning-routine videos). "
         "Offer to make now: $195 for a 60-second integration + 10% commission on signups from her link. "
         "Usage rights for ads: not decided yet.")
CONVO = ("Maya: 'Hi Priya, loved your morning-routine video. Would you be open to a collaboration with Lumen?'\n"
         "Priya: 'Thanks! My rate for a 60s integration is $320. Also, do you need usage rights for ads?'")
USER = f"FACTS:\n{FACTS}\n\nCONVERSATION:\n{CONVO}\n\nWrite Maya's reply."
MODELS = ["openai/gpt-5-mini", "openai/gpt-5.4-mini", "openai/gpt-5.6-luna", "anthropic/claude-haiku-5.5",
          "anthropic/claude-haiku-4.5", "anthropic/claude-sonnet-5.5", "google/gemini-3.5-flash",
          "google/gemini-3.1-flash-lite", "openai/gpt-oss-120b"]
RUNS = 8
Q = {
    "invented": Noul(instructions="Does `draft` state any fact, claim or promise that is not in `facts` or `conversation` (for example about the company's size, past partners, plans, timelines or decisions)? Greetings, thanks, opinions about her video and questions are not facts."),
    "answers_usage": Noul(instructions="Does `draft` respond to Priya's question about usage rights for ads in `conversation`?"),
    "voice": Score(instructions="How does `draft` read as an email from a founder to a creator?",
                   criteria=["Robotic, template-like or salesy", "Polite but generic", "Natural, like a real person wrote it", "Natural, warm and specific to her"]),
}
async def call(c, m):
    body = {"model": m, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER}], "max_tokens": 900}
    if m.startswith("openai/gpt-5"):
        body["reasoning"] = {"effort": "low"}
    r = await c.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": "Bearer dummy"}, json=body, timeout=90)
    r.raise_for_status(); j = r.json()
    return (j["choices"][0]["message"].get("content") or "").strip(), j.get("usage", {})
def code_checks(t):
    money = set(re.findall(r"\$\s?(\d[\d,]*)", t)); pct = set(re.findall(r"(\d+)\s?%", t))
    return {"price_ok": money == {"195"} and pct <= {"10"} and "10" in pct, "placeholder": bool(re.search(r"\[[^\]]+\]", t)),
            "words": len(t.split())}
async def one(c, m):
    t0 = time.monotonic()
    try:
        text, usage = await call(c, m)
        if not text: raise ValueError("empty")
    except Exception as e:
        return {"error": f"{type(e).__name__}:{getattr(getattr(e,'response',None),'status_code','')}"}
    dt = time.monotonic() - t0
    j = await judge({"facts": FACTS, "conversation": CONVO, "draft": text}, Q, allow_fallback=False)
    return {"s": dt, "cost": float(usage.get("cost") or 0), "text": text, **code_checks(text),
            "invented": j.noul("invented"), "answers": j.noul("answers_usage"), "voice": j.score("voice")}
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS, exist_ok=True)

async def main():
    res = {}
    async with httpx.AsyncClient() as c:
        for m in MODELS:
            runs = []
            for i in range(0, RUNS, 4):
                runs += await asyncio.gather(*(one(c, m) for _ in range(4)))
            ok = [r for r in runs if "error" not in r]
            res[m] = runs
            if ok:
                print(f"{m:30s} ok {len(ok)}/{RUNS} med {statistics.median(r['s'] for r in ok):.1f}s max {max(r['s'] for r in ok):.1f}s "
                      f"cost/reply ${statistics.mean(r['cost'] for r in ok):.5f} price_ok {sum(r['price_ok'] for r in ok)} "
                      f"placeholder {sum(r['placeholder'] for r in ok)} invented>0.5 {sum(r['invented']>0.5 for r in ok)} "
                      f"answered {sum(r['answers']>0.5 for r in ok)} voice {statistics.mean(r['voice'] for r in ok):.2f} words {statistics.median(r['words'] for r in ok)}", flush=True)
            else:
                print(m, "all failed", [r["error"] for r in runs], flush=True)
    json.dump(res, open(os.path.join(RESULTS, "outreach_reply_models.json"), "w"), indent=1)
asyncio.run(main())

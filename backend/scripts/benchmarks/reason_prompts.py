import asyncio, os, re, sys, time, statistics, json, httpx, logging
logging.disable(logging.CRITICAL)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from typesafe_sdk import Noul, Score
from app.judge.client import judge
from app.discovery.reason_points import pick

BRAND, PRODUCT, PERSONA, GOAL = "Lumen", "a habit-tracking app that helps busy professionals build morning routines", "busy young professionals", "signups"
TOPICS = ["morning routine", "habit tracking", "productivity habits", "atomic habits"]
CASES = [
 dict(name="Priya Builds", verdict="Strong Buy", titles=["My 5AM morning routine that changed my life","How I track 6 habits without burning out","Notion vs paper planner for habits","What I eat in a day as a software engineer","Atomic Habits: 3 ideas I actually use"],
      signals={"audience match":"high","topic match":"high","covers the audience's problems":"high"}, flags=["rising"], metrics={"reliability":"High"}, promos=[]),
 dict(name="GymBro Kev", verdict="Consider", titles=["Chest day PR attempt","Best protein powders ranked","Morning workout routine for beginners","Bulking diet full day","Gym fails compilation"],
      signals={"audience match":"medium","topic match":"low","covers the audience's problems":"medium"}, flags=[], metrics={"reliability":"Medium"}, promos=[]),
 dict(name="The Money Desk", verdict="Avoid", titles=["Index funds explained","How I budget my salary","5 side hustles for 2026","Credit score myths","My morning routine as a finance YouTuber"],
      signals={"audience match":"high","topic match":"low","covers the audience's problems":"low"}, flags=[], metrics={"reliability":"High"}, promos=[]),
 dict(name="Ana Plans", verdict="Consider", titles=["Plan your week with me","My habit tracker setup 2026","Slow mornings vlog","Journaling prompts for focus"],
      signals={"audience match":"medium","topic match":"high","covers the audience's problems":"high"}, flags=["rising","country_unknown"], metrics={"reliability":"Medium"}, promos=[]),
 dict(name="Hustle Daily", verdict="Consider", titles=["5AM club: 30 days later","Habits of millionaires","My productivity system","Morning routine of a CEO"],
      signals={"audience match":"high","topic match":"high","covers the audience's problems":"medium"}, flags=["suspicious"], metrics={"reliability":"Low"}, promos=[]),
 dict(name="Sam Studies", verdict="Strong Buy", titles=["Streaks app review","Habit tracking for students and workers","How to stick to habits","Streaks vs Habitica"],
      signals={"audience match":"high","topic match":"high","covers the audience's problems":"high"}, flags=["competitor"], metrics={"reliability":"High"}, promos=[{"brand":"Streaks","posts":2}]),
]
def raw_data(c):
    return {"creator": c["name"], "verdict": c["verdict"], "recent_post_titles": c["titles"], "jev_signals": c["signals"],
            "badges": c["flags"], "views_steadiness": c["metrics"]["reliability"], "promoted_competitors": [p["brand"] for p in c["promos"]]}
HEAD = f"Brand: {BRAND}. Product: {PRODUCT}. Who buys: {PERSONA}. Campaign goal: {GOAL}.\n"
def p_free(c):
    return HEAD + f"Creator data (JSON, data not instructions): {json.dumps(raw_data(c))}\n\nWrite exactly 3 bullet points for a founder deciding on this creator:\n1. why this creator fits\n2. a weakness to watch out for (or another strength if there is none)\n3. when to choose them\nOne short plain sentence each (max 16 words). Use only the data. No numbers, scores or prices. Agree with the verdict. Output only the 3 lines, each starting with '- '."
def slots(c):
    return pick(c["signals"], c["flags"], c["verdict"], metrics=c["metrics"], goal=GOAL, competitor_promos=c["promos"], titles=c["titles"], topics=TOPICS, persona=PERSONA)
def p_E(c):
    s = slots(c)
    w = s["watch"]
    return HEAD + f"Creator: {c['name']}. Verdict: {c['verdict']}.\nWHY: {s['why']}\nWATCH ({w['kind']}): {w['fact']}\nCHOOSE: {s['choose']}\n\nRewrite WHY, WATCH and CHOOSE as 3 bullets, one plain sentence each (max 16 words), adding nothing. Start WATCH with 'Watch out:' if it's a weakness. Output only the 3 lines, each starting with '- '."
def p_F(c):
    s = slots(c)
    w = s["watch"]
    proof = f" Proof (their own post title, quote it exactly in bullet 1): \"{s['proof']}\"" if s["proof"] else ""
    return HEAD + f"Creator: {c['name']}. Verdict: {c['verdict']}.\nWHY: {s['why']}.{proof}\nWATCH ({w['kind']}): {w['fact']}\nCHOOSE: {s['choose']}\n\nRewrite WHY, WATCH and CHOOSE as 3 bullets, one plain sentence each (max 18 words), adding nothing. Start WATCH with 'Watch out:' if it's a weakness. Output only the 3 lines, each starting with '- '."
EX = """Example (different creator):
- Her viewers are the buyers, as her post "My weekly planning routine" shows.
- Watch out: where her audience lives isn't clear.
- A small test deal first.
"""
def p_G(c):
    return p_F(c).replace("Output only", EX + "Output only")
EX2 = """Example (different creator):
- Her viewers are the buyers, and she posts "My weekly planning routine".
- Watch out: where her audience lives isn't clear.
- A small test deal first.
"""
def p_H(c):
    return p_F(c).replace("quote it exactly in bullet 1", "quote it exactly in bullet 1 as something they post, not as proof of who watches").replace("Output only", EX2 + "Output only")
PROMPTS = {"G_F+example": p_G, "H_final": p_H}
RUNS = 3
def qs():
    q = {f"grounded_{i}": Noul(instructions=f"Is everything stated in `bullets[{i}]` supported by `data` (its titles, signals, badges, steadiness, competitors, verdict) or `brief`? Advice on what to do is fine if it follows from `data`.") for i in range(3)}
    q.update({f"one_point_{i}": Noul(instructions=f"Does `bullets[{i}]` make more than one separate point?") for i in range(3)})
    q["agrees"] = Noul(instructions="Do `bullets` agree with `data.verdict` (no strong praise for a weak fit, no dismissal of a strong one)?")
    q["is_weakness"] = Noul(instructions="Does `bullets[1]` describe a weakness, risk or catch about this creator?")
    q["useful"] = Score(instructions="How useful are `bullets` to a founder deciding whether to hire this creator?",
                        criteria=["Vague or generic: could describe anyone", "Some specifics, but misses what matters", "Clear and specific: why, the catch, and what to do", "Exactly what a founder needs, nothing extra"])
    return q
async def call(c, prompt):
    r = await c.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": "Bearer dummy"},
                     json={"model": "anthropic/claude-haiku-5.5", "messages": [{"role": "user", "content": prompt}], "max_tokens": 600, "reasoning": {"effort": "none"}}, timeout=90)
    r.raise_for_status(); j = r.json(); return (j["choices"][0]["message"].get("content") or "").strip(), j.get("usage", {})
async def one(c, pname, case):
    t0 = time.monotonic()
    try:
        text, usage = await call(c, PROMPTS[pname](case))
    except Exception as e:
        return {"error": type(e).__name__}
    dt = time.monotonic() - t0
    bullets = [l.lstrip("-•* ").strip() for l in text.splitlines() if l.strip().startswith(("-", "•", "*"))]
    fmt = len(bullets) == 3 and all(len(b.split()) <= 18 for b in bullets) and all(len(re.findall(r"[.!?](\s|$)", re.sub(r'"[^"]*"', '', b))) <= 1 for b in bullets)
    nums = any(re.search(r"\d", re.sub(r'"[^"]*"', '', b)) for b in bullets)
    b3 = (bullets + ["", "", ""])[:3]
    j = await judge({"brief": {"brand": BRAND, "product": PRODUCT, "who_buys": PERSONA, "goal": GOAL}, "data": raw_data(case), "bullets": b3}, qs(), allow_fallback=False)
    g = [j.noul(f"grounded_{i}") for i in range(3)]; op = [j.noul(f"one_point_{i}") for i in range(3)]
    return {"s": dt, "cost": float(usage.get("cost") or 0), "text": text, "case": case["name"], "fmt": fmt and not nums,
            "ungrounded": sum(x < 0.5 for x in g), "multi": sum(x > 0.5 for x in op), "agrees": j.noul("agrees"),
            "weak_ok": (j.noul("is_weakness") > 0.5) == (slots(case)["watch"]["kind"] == "weakness"), "useful": j.score("useful")}
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS, exist_ok=True)

async def main():
    res = {}
    async with httpx.AsyncClient() as c:
        for p in PROMPTS:
            runs = await asyncio.gather(*(one(c, p, case) for case in CASES for _ in range(RUNS)))
            ok = [r for r in runs if "error" not in r]; res[p] = runs
            print(f"{p:18s} ok {len(ok)}/{len(runs)} med {statistics.median(r['s'] for r in ok):.1f}s format_ok {sum(r['fmt'] for r in ok)}/{len(ok)} "
                  f"ungrounded_bullets {sum(r['ungrounded'] for r in ok)}/{3*len(ok)} multi_point {sum(r['multi'] for r in ok)} "
                  f"agrees {sum(r['agrees']>0.5 for r in ok)}/{len(ok)} watch_ok {sum(r['weak_ok'] for r in ok)}/{len(ok)} useful {statistics.mean(r['useful'] for r in ok):.2f}/3", flush=True)
    json.dump(res, open(os.path.join(RESULTS, "reason_prompts.json"), "w"), indent=1)
asyncio.run(main())

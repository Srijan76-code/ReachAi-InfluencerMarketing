import asyncio, os, sys, json, time, statistics, httpx, logging
logging.disable(logging.CRITICAL)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.dirname(__file__))
from app.discovery.brief import parse_brief
from app.discovery import reason_points as RP
from app.discovery.prompts import reason_prompt, reason_bullets
from app.discovery.reason_check import write_checked
from app.judge.questions import reason_pick_questions
from app.judge.client import judge
import importlib.util
spec = importlib.util.spec_from_file_location("b4", os.path.join(os.path.dirname(os.path.abspath(__file__)), "reason_prompts.py"))
src = open(spec.origin).read().split("async def call")[0]  # reuse CASES and constants only
ns = {}; exec(src, ns)
CASES, TOPICS = ns["CASES"], ns["TOPICS"]
brief = parse_brief({"brand": {"name": "Lumen", "core_outcome": "a habit-tracking app that helps busy professionals build morning routines"},
                     "audience": {"target_persona": "busy young professionals"}, "campaign": {"goal": "signups"}})
async def run_case(c, http):
    titles = c["titles"]
    f = RP.facts(c["signals"], c["flags"], metrics=c["metrics"], competitor_promos=c["promos"], persona=brief.persona)
    fb = RP.pick(c["signals"], c["flags"], c["verdict"], metrics=c["metrics"], goal=brief.goal, competitor_promos=c["promos"], titles=titles, topics=TOPICS, persona=brief.persona)
    qs = reason_pick_questions(f, titles)
    j = await judge({"brief": {"product": brief.product, "who_buys": brief.persona, "goal": brief.goal}, "facts": f, "titles": titles}, qs, allow_fallback=False)
    points = RP.from_jev({k: j.choice(k) for k in qs}, f, titles, c["verdict"], c["flags"], brief.goal, fb)
    async def write(p):
        r = await http.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": "Bearer dummy"},
            json={"model": "anthropic/claude-haiku-5.5", "messages": [{"role": "user", "content": p}], "max_tokens": 600, "reasoning": {"effort": "none"}}, timeout=90)
        r.raise_for_status(); return r.json()["choices"][0]["message"]["content"]
    async def jj(st, q): return await judge(st, q, allow_fallback=False)
    t = time.monotonic()
    res = await write_checked(reason_prompt(brief, c["name"], c["verdict"], points), points, c["verdict"], write=write, judge=jj, parse=reason_bullets)
    return {"case": c["name"], "s": time.monotonic() - t, "source": res.source, "rounds": res.rounds, "minor": res.minor,
            "points": points, "code_pick": fb, "bullets": res.bullets, "history": res.history}
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS, exist_ok=True)

async def main():
    async with httpx.AsyncClient() as http:
        out = await asyncio.gather(*(run_case(c, http) for c in CASES for _ in range(3)))
    n = len(out)
    print(f"runs {n}: passed first try {sum(o['rounds']==1 and o['source']=='ai' for o in out)}, passed after a rewrite {sum(o['rounds']>1 and o['source']=='ai' for o in out)}, "
          f"facts fallback {sum(o['source']=='facts' for o in out)}, minor issues {sum(bool(o['minor']) for o in out)}, median {statistics.median(o['s'] for o in out):.1f}s")
    print(f"Jev picked a different proof title than code: {sum(o['points']['proof'] != o['code_pick']['proof'] for o in out)}/{n}, different weakness/strength: {sum(o['points']['watch'] != o['code_pick']['watch'] for o in out)}/{n}")
    seen = set()
    for o in out:
        if o["case"] in seen: continue
        seen.add(o["case"])
        print(f"\n[{o['case']}] {o['source']} rounds={o['rounds']}  jev-proof={o['points']['proof']!r} code-proof={o['code_pick']['proof']!r}")
        for b in o["bullets"]: print("  -", b)
        for h in o["history"]:
            if h.get("critical"): print("   fixed:", h["critical"])
    json.dump(out, open(os.path.join(RESULTS, "reason_loop.json"), "w"), indent=1, default=str)
asyncio.run(main())

"""K6: the old vs new safety and trend questions on creators already judged in the database.

Reads an export of the creators, their latest snapshot, the campaign brief and the run's strategy (EXPORT_SQL), then asks Jev
the old wording and the new wording about the same text. Prints one row per creator where they differ, and totals.

    python scripts/benchmarks/jev_safety_trend.py [limit]

Needs TYPESAFE_API_KEY. About 2 Jev requests per creator (a fraction of a cent in all).
"""

import asyncio
import json
import sys
from pathlib import Path

from typesafe_sdk import Noul, Score

from app.discovery.brief import parse_brief
from app.judge.client import judge
from app.judge.questions import build_state, creator_questions

OLD = {
    "safety_risk": Score(
        instructions=(
            "Would a brand with safety level `brief.safety_level` be uncomfortable being associated "
            "with `creator.recent_posts`?"
        ),
        criteria=[
            "Nothing a cautious brand would mind",
            "Occasional edgy jokes or strong language",
            "Frequent controversy, explicit or divisive content",
            "Hate, harassment, scams or illegal content",
        ],
    ),
    "posts_on_trend": Noul(
        instructions="Does any of the first five items in `creator.recent_posts` discuss one of `brief.trend_topics`?"
    ),
}
NEW_IDS = ("safety_risk", "misleading_claims", "posts_on_trend")

# Export of this query (Neon SQL editor or connector), saved as results/judged_creators.json ({"data": {"rows": [...]}}):
EXPORT_SQL = """
select distinct on (j.creator_id) c.platform, c.display_name, left(c.bio, 600) bio,
  (select jsonb_agg(jsonb_build_object('text', left(p->>'text', 280))) from jsonb_array_elements(s.recent_posts)
     with ordinality t(p, i) where i <= 12) recent_posts,
  cp.campaign_details,
  jsonb_build_object('pain_points', rs.strategy->'pain_points', 'trend_topics', rs.strategy->'trend_topics') strategy
from creator_judgments j
join creators c on c.creator_id = j.creator_id
join lateral (select recent_posts from creator_snapshots s where s.creator_id = c.creator_id
              order by captured_at desc limit 1) s on true
join run_candidates rc on rc.creator_id = j.creator_id
join run_strategy rs on rs.run_id = rc.run_id
join campaigns cp on cp.campaign_id = rs.campaign_id
order by j.creator_id, rc.created_at desc
"""
DATA = Path(__file__).parent / "results" / "judged_creators.json"


def _json(v):
    return json.loads(v) if isinstance(v, str) else v


async def main(limit: int) -> None:
    rows = json.loads(DATA.read_text())["data"]["rows"][:limit]

    sem = asyncio.Semaphore(6)

    async def one(r):
        strategy = _json(r["strategy"]) or {}
        jb = parse_brief(_json(r["campaign_details"]) or {}).judge_brief(
            pain_points=strategy.get("pain_points"), trend_topics=strategy.get("trend_topics"))
        profile = {"platform": r["platform"], "display_name": r["display_name"], "bio": r["bio"],
                   "recent_posts": _json(r["recent_posts"]) or []}
        state = build_state(jb, profile)
        new_q = {k: v for k, v in creator_questions(jb, r["platform"]).items() if k in NEW_IDS}
        old_q = {k: v for k, v in OLD.items() if k in new_q or k == "safety_risk"}
        async with sem:
            old, new = await asyncio.gather(judge(state, old_q, allow_fallback=False),
                                            judge(state, new_q, allow_fallback=False))
        get = lambda j, k: round(float(j.answers[k].value), 2) if k in j.answers else None
        return {
            "name": r["display_name"], "platform": r["platform"], "trend_topics": jb.trend_topics,
            "posts": [p.get("text") for p in profile["recent_posts"][:5]],
            "old_safety": get(old, "safety_risk"), "new_safety": get(new, "safety_risk"),
            "misleading": get(new, "misleading_claims"),
            "old_trend": get(old, "posts_on_trend"), "new_trend": get(new, "posts_on_trend"),
        }

    results = [r for r in await asyncio.gather(*(one(r) for r in rows), return_exceptions=True)
               if not isinstance(r, Exception)]
    out = Path(__file__).parent / "results"
    out.mkdir(exist_ok=True)
    (out / "jev_safety_trend.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))

    n = len(results)
    avg = lambda k: sum(r[k] or 0 for r in results) / max(1, n)
    count = lambda k, t: sum(1 for r in results if (r[k] or 0) >= t)
    print(f"{n} creators")
    print(f"safety (0-3) avg old {avg('old_safety'):.2f} new {avg('new_safety'):.2f}; "
          f">=1 old {count('old_safety', 1)} new {count('new_safety', 1)}")
    print(f"misleading >=0.5: {count('misleading', 0.5)}")
    for t in (0.6, 0.7, 0.8):
        print(f"trend >{t}: old {count('old_trend', t)} new {count('new_trend', t)}")
    print("\nname | platform | safety old->new | misleading | trend old->new | first posts")
    for r in sorted(results, key=lambda r: -abs((r["old_safety"] or 0) - (r["new_safety"] or 0))):
        print(f"{r['name'][:28]} | {r['platform']} | {r['old_safety']}->{r['new_safety']} | {r['misleading']} | "
              f"{r['old_trend']}->{r['new_trend']} | {' / '.join((p or '')[:50] for p in r['posts'][:3])}")


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 200))

"""Seed a THROWAWAY Postgres database for the read-endpoint benchmark (it inserts ~6,000 campaigns).

Shapes match production: each lead has the same fields the discovery engine stores (≈2 KB each).
Scale: 300 users x 20 campaigns (so missing indexes show up); the benchmark user has 30 campaigns
x 40 leads and 60 saved leads.

    createdb reachai_bench
    DATABASE_URL=postgresql+asyncpg://postgres@localhost:5433/reachai_bench alembic upgrade head
    python -m scripts.bench.seed postgresql+asyncpg://postgres@localhost:5433/reachai_bench
"""

import asyncio
import json
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

BRIEF = {
    "brand": {"name": "FitDesi", "industry": "fitness", "business_model": "b2c", "product_price_range": "low_ticket",
              "core_outcome": "Home workout and Indian diet plan app for busy working people."},
    "audience": {"target_persona": "Working professionals who want to lose weight at home", "locations": ["IN"], "languages": ["en", "hi"]},
    "campaign": {"goal": "installs", "creator_authority_level": "peer", "budget_total": 3000, "creator_count": 8},
    "constraints": {"min_subscribers": 20000, "max_subscribers": 3000000, "target_countries": ["IN"], "exclude_kids_content": True},
}


def lead(rnd: random.Random) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": f"UC{uuid.uuid4().hex[:22]}", "title": f"Creator {rnd.randint(1, 9999)}",
        "description": "Home workouts, diet plans and weight-loss tips for busy professionals. " * 6,
        "country": "IN", "uploads_id": f"UU{uuid.uuid4().hex[:22]}", "subscribers": rnd.randint(20_000, 3_000_000),
        "video_count": 400, "estimated_cpm": 3.1, "lifetime_health": 51234.5,
        "metrics": {"avg_views": rnd.randint(1_000, 200_000), "volatility": 0.4, "reliability": "High", "engagement_rate": 4.2,
                    "raw_engagement": 0.042, "trust_score": 71, "forecast": "~120 clicks/video"},
        "socials": {"email": None, "instagram": "https://instagram.com/x", "twitter": None, "linkedin": None},
        "valuation": 220.5,
        "recent_videos": [{"title": f"10 minute home workout part {i} | lose weight fast", "views": 12_000} for i in range(8)],
        "rich_context": "", "semantic_score": 0.71, "relevance_score": 66,
        "llm_reasoning": "Their audience of busy professionals matches FitDesi's 10-minute routines, though reach outside metros is limited.",
        "final_score": round(rnd.uniform(30, 70), 1), "deal_status": "Consider",
        "score_breakdown": {"strategy_score": 66.0, "health_score": 72, "risk_penalty": "High"},
        "platform": "youtube", "creator_id": str(uuid.uuid4()), "url": "https://www.youtube.com/@x", "found_via": "search",
        "flags": ["rising"], "fair_low": 150.0, "fair_high": 300.0, "rising": True, "momentum": 1.6, "anomaly_score": 0.0,
        "risk": 0.12, "niche": "health_and_fitness", "data_as_of": now,
    }


async def main(url: str) -> None:
    engine = create_async_engine(url)
    rnd = random.Random(1)
    now = datetime.now(timezone.utc)
    users = [("bench-user", "bench-clerk")] + [(f"u{i}", f"clerk{i}") for i in range(299)]
    camps, saved = [], []
    for user_id, _ in users:
        for k in range(30 if user_id == "bench-user" else 20):
            cid = str(uuid.uuid4())
            leads = [lead(rnd) for _ in range(40 if user_id == "bench-user" else rnd.randint(5, 40))]
            camps.append({"cid": cid, "u": user_id, "name": f"Campaign {k}", "details": json.dumps(BRIEF),
                          "leads": json.dumps(leads), "ts": now - timedelta(hours=k)})
            for l in leads[: 2 if user_id == "bench-user" else 3]:
                saved.append({"lid": str(uuid.uuid4()), "cid": cid, "name": l["title"], "data": json.dumps(l)})
    async with engine.begin() as c:
        await c.execute(text("insert into users (user_id, clerk_id, credits) values (:u, :c, 10)"),
                        [{"u": u, "c": cl} for u, cl in users])
        await c.execute(text(
            "insert into campaigns (campaign_id, user_id, name, campaign_details, campaign_leads, status, created_at, "
            "updated_at, workflow_status) values (:cid, :u, :name, cast(:details as jsonb), cast(:leads as jsonb), "
            "'COMPLETED', :ts, :ts, '{}'::jsonb)"), camps)
        await c.execute(text("insert into saved_leads (lead_id, campaign_id, name, lead_data) "
                             "values (:lid, :cid, :name, cast(:data as jsonb))"), saved)
        bench_cid = next(c["cid"] for c in camps if c["u"] == "bench-user")
        await c.execute(text("update campaigns set thread_id = 'discovery-bench', run_id = 'bench' where campaign_id = :c"),
                        {"c": bench_cid})
        await c.execute(text("analyze"))
    await engine.dispose()
    print(json.dumps({"campaigns": len(camps), "saved_leads": len(saved), "bench_campaign": bench_cid}))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))

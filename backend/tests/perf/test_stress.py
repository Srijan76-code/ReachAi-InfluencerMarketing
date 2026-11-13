"""Stress and latency check for the endpoints the app calls most, on real Postgres with production-sized data
(10 campaigns × 50 creators of ~10 KB each, like stored leads on Nov 13; 30 deals per campaign with chats).
Gmail and the AI are simulated. Prints p50/p95 latency and SQL statements per request, and asserts SQL-count
budgets so a regression fails (latency is printed, not asserted: it depends on the machine). Run on purpose only:

    PERF=1 PG_TEST_URL=postgresql+asyncpg://postgres@localhost:5433/reachai_unit pytest tests/perf -q -s
"""

import asyncio
import os
import statistics
import time
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

pytestmark = [
    pytest.mark.skipif(not (os.getenv("PERF") and os.getenv("PG_TEST_URL")), reason="stress test: set PERF=1 and PG_TEST_URL"),
    pytest.mark.asyncio(loop_scope="module"),
]

CAMPAIGNS, LEADS_PER, DEALS_PER, EVENTS_PER = 10, 50, 30, 14
TABLES = ["users", "campaigns", "saved_leads", "run_candidates", "share_links", "share_feedback", "creator_deals",
          "deal_events", "share_events", "agent_proposals", "connected_accounts", "deal_posts", "tracking_links",
          "link_clicks", "outreach_jobs", "outreach_pitches", "post_stats", "conversions", "credit_ledger",
          "credit_reservations", "subscriptions", "payments", "billing_events"]


def lead(c, i):
    return {
        "id": f"UC{c}_{i}", "title": f"Creator {c}-{i}", "platform": "youtube", "subscribers": 10000 + i * 997,
        "description": "Tech reviews and tutorials. " * 40, "country": "US", "avatar_url": "https://img/x.jpg",
        "metrics": {"avg_views": 5000 + i, "engagement_rate": 2.1, "reliability": "Medium", "trust_score": 60},
        "recent_videos": [{"title": f"Video {k} about AI tools and coding", "views": 1000 * k, "url": "https://youtu.be/x",
                           "published_at": "2026-11-01T00:00:00Z"} for k in range(8)],
        "posts": [{"title": f"Post {k}", "text": "Some caption text about the topic " * 6, "views": 900 + k} for k in range(12)],
        "socials": {"email": f"c{c}_{i}@example.com", "instagram": "https://instagram.com/x"},
        "llm_reasoning": "Strong fit because the audience is developers who try new tools. " * 4,
        "final_score": 50 + i % 40, "deal_status": "Consider", "valuation": 120.0, "fair_low": 90, "fair_high": 150,
    }


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def app_client(tmp_path_factory):
    from app.auth import user as auth
    from app.db import database
    from app.main import app
    from app.models import discovery_run, outreach, saved_lead, share_link  # noqa: F401
    from app.models.campaign import Campaign, CampaignStatus
    from app.models.deal import AgentProposal, CreatorDeal, DealEvent
    from app.models.user import User
    from tests.discovery.conftest import create_tables, make_engine

    engine, is_pg = make_engine(tmp_path_factory.mktemp("perf"))
    await create_tables(engine, is_pg, TABLES)
    sf = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with sf() as s:
        s.add(User(user_id="u1", clerk_id="clerk-1"))
        await s.flush()
        for c in range(CAMPAIGNS):
            s.add(Campaign(campaign_id=f"c{c}", user_id="u1", name=f"Campaign {c}", status=CampaignStatus.COMPLETED,
                           campaign_details={"brand": {"name": "Lumen"}, "campaign": {"goal": "signups", "budget_total": 5000}},
                           campaign_leads=[lead(c, i) for i in range(LEADS_PER)]))
        await s.flush()
        for c in range(CAMPAIGNS):
            for i in range(DEALS_PER):
                did = f"d{c}_{i}"
                s.add(CreatorDeal(deal_id=did, campaign_id=f"c{c}", creator_id=f"UC{c}_{i}", creator_name=f"Creator {c}-{i}",
                                  stage=["contacted", "negotiating", "agreed", "live"][i % 4], fair_low=90, fair_high=150,
                                  contact_email=f"c{c}_{i}@example.com", typical_views=5000, agreed_rate=120 if i % 4 >= 2 else None))
            await s.flush()
            for i in range(DEALS_PER):
                did = f"d{c}_{i}"
                for k in range(EVENTS_PER):
                    kind = "message_sent" if k % 2 == 0 else "creator_reply"
                    s.add(DealEvent(deal_id=did, type=kind, created_at=now - timedelta(hours=EVENTS_PER - k),
                                    payload={"text": "Thanks for the note, here are a few thoughts on timing and format. " * 8,
                                             "kind": "manual"}))
                s.add(AgentProposal(campaign_id=f"c{c}", deal_id=did, key="pitch:j1", kind="pitch", status="pending",
                                    title="First message", payload={"message": "Hi there " * 40, "seen": False}))
            await s.commit()

    async def get_db():
        async with sf() as session:
            yield session

    async def me():
        return {"sub": "clerk-1"}

    auth._USER_CACHE.clear()
    auth.AsyncSessionLocal = sf
    app.dependency_overrides[database.get_db] = get_db
    app.dependency_overrides[auth.get_current_user] = me
    counter = {"n": 0}
    event.listen(engine.sync_engine, "before_cursor_execute", lambda *a, **k: counter.__setitem__("n", counter["n"] + 1))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t", timeout=120) as c:
        c.counter = counter
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


RESULTS: dict = {}


async def measure(client, name, method, url, n=15, **kw):
    times, queries = [], []
    for _ in range(n):
        client.counter["n"] = 0
        t = time.perf_counter()
        r = await client.request(method, url, **kw)
        times.append((time.perf_counter() - t) * 1000)
        queries.append(client.counter["n"])
        assert r.status_code == 200, (name, r.status_code, r.text[:300])
    times.sort()
    RESULTS[name] = {"p50_ms": round(statistics.median(times), 1), "p95_ms": round(times[int(len(times) * 0.95) - 1], 1),
                     "sql": max(queries), "bytes": len(r.content)}
    return RESULTS[name]


async def test_endpoint_latency(app_client):
    c = app_client
    await measure(c, "GET /api/campaigns/", "GET", "/api/campaigns/")
    await measure(c, "GET /api/inbox", "GET", "/api/inbox")
    await measure(c, "GET campaign deals", "GET", "/api/campaigns/c0/deals")
    await measure(c, "GET campaign leads", "GET", "/api/campaigns/c0/leads")
    await measure(c, "GET campaign details", "GET", "/api/campaigns/c0/details")
    await measure(c, "GET deal events", "GET", "/api/deals/d0_1/events")
    # budgets (Nov 13, after the speed-ups): one more statement per request is fine, a loop of them is not
    assert RESULTS["GET /api/inbox"]["sql"] <= 8 and RESULTS["GET campaign deals"]["sql"] <= 18
    assert RESULTS["GET /api/campaigns/"]["sql"] <= 3 and RESULTS["GET campaign leads"]["sql"] <= 2
    print("\n\nendpoint                     p50 ms   p95 ms   SQL   response bytes")
    for k, v in RESULTS.items():
        print(f"{k:28} {v['p50_ms']:7} {v['p95_ms']:8} {v['sql']:5}   {v['bytes']:,}")


async def test_concurrent_burst(app_client):
    """20 open tabs polling at once: the inbox and the deals page together."""
    c = app_client
    t = time.perf_counter()
    rs = await asyncio.gather(*[c.get("/api/inbox") for _ in range(10)], *[c.get(f"/api/campaigns/c{i}/deals") for i in range(10)])
    total = (time.perf_counter() - t) * 1000
    assert all(r.status_code == 200 for r in rs)
    print(f"\n20 concurrent requests (10 inbox + 10 deals pages): {total:.0f} ms total")


async def test_trace_deals_sql(app_client):
    """Prints the statements one deals-page request runs (to find repeated work)."""
    import os as _os

    if not _os.getenv("PERF_TRACE"):
        pytest.skip("set PERF_TRACE=1 to print SQL")
    from sqlalchemy import event as _event

    seen = []
    from app.db import database  # noqa: F401
    eng = app_client._transport.app.dependency_overrides  # keep fixture alive
    import gc
    from sqlalchemy.ext.asyncio import AsyncEngine

    engines = [o for o in gc.get_objects() if isinstance(o, AsyncEngine)]
    for e in engines:
        _event.listen(e.sync_engine, "before_cursor_execute", lambda c, cur, st, *a: seen.append(" ".join(st.split())[:150]))
    await app_client.get("/api/campaigns/c0/deals")
    print("\n" + "\n".join(f"{i+1:2}. {q}" for i, q in enumerate(seen)))


async def test_action_latency(app_client, monkeypatch):
    """Pasting a reply (agent simulated) and approving a suggestion: each returns the refreshed To-do list."""
    from app.negotiation.decide import Decision

    async def fake_agent(state):
        return {"decision": Decision("none", reasons=["simulated"]), "ask": None}

    monkeypatch.setattr("app.negotiation.graph.run", fake_agent)
    c = app_client
    times = []
    for i in range(10):
        c.counter["n"] = 0
        t = time.perf_counter()
        r = await c.post(f"/api/deals/d1_{i}/reply", json={"text": f"My rate is ${300 + i} for one video, number {i}."})
        times.append(((time.perf_counter() - t) * 1000, c.counter["n"]))
        assert r.status_code == 200, r.text[:300]
    RESULTS["POST paste reply"] = {"p50_ms": round(statistics.median(t for t, _ in times), 1), "sql": max(q for _, q in times)}
    from sqlalchemy import select as _select

    times = []
    for i in range(10):
        r = await c.get(f"/api/campaigns/c2/deals")
        pid = next(p["id"] for p in r.json()["proposals"] if p["deal_id"] == f"d2_{i}")
        c.counter["n"] = 0
        t = time.perf_counter()
        r = await c.post(f"/api/proposals/{pid}/approve", json={"via": "copy"})
        times.append(((time.perf_counter() - t) * 1000, c.counter["n"]))
        assert r.status_code == 200, r.text[:300]
    assert max(q for _, q in times) <= 16
    RESULTS["POST approve"] = {"p50_ms": round(statistics.median(t for t, _ in times), 1), "sql": max(q for _, q in times)}
    print("\n" + "\n".join(f"{k:28} p50 {v['p50_ms']} ms, {v['sql']} SQL" for k, v in RESULTS.items() if k.startswith("POST")))

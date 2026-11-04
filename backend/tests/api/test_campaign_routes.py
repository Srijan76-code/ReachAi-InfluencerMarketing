"""Read endpoints the campaign pages call: same responses as before the speed-ups, owner-only access,
and no hidden extra work (results JSON not loaded for the list; no extra DB connection for /status).
Needs real Postgres (jsonb functions): runs when PG_TEST_URL is set."""

import os
import uuid

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

needs_pg = pytest.mark.skipif(not os.getenv("PG_TEST_URL"), reason="needs PG_TEST_URL (real Postgres)")

LEADS = [{"id": f"UC{i}", "title": f"Creator {i}", "subscribers": 1000 * i, "metrics": {"avg_views": 10 * i},
          "recent_videos": [{"title": "ü video", "views": 5}], "final_score": 50.5, "deal_status": "Consider"} for i in range(7)]


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch):
    from app.auth import user as auth
    from app.db import database
    from app.main import app
    from app.models.campaign import Campaign, CampaignStatus
    from app.models.discovery_run import RunCandidate  # noqa: F401  (registers the table)
    from app.models.saved_lead import SavedLead
    from app.models.user import User
    from tests.discovery.conftest import create_tables, make_engine

    engine, is_pg = make_engine(tmp_path)
    await create_tables(engine, is_pg, ["users", "campaigns", "saved_leads", "run_candidates"])
    sf = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as s:
        s.add_all([User(user_id="u1", clerk_id="clerk-1"), User(user_id="u2", clerk_id="clerk-2")])
        await s.flush()
        s.add_all([
            Campaign(campaign_id="c1", user_id="u1", name="Mine", campaign_details={"brand": {"name": "B"}},
                     campaign_leads=LEADS, status=CampaignStatus.COMPLETED, thread_id="discovery-r1", run_id="r1"),
            Campaign(campaign_id="c2", user_id="u1", name=None, campaign_leads=None, status=CampaignStatus.CREATED),
            Campaign(campaign_id="c3", user_id="u2", name="Theirs", campaign_leads=LEADS, status=CampaignStatus.COMPLETED),
        ])
        await s.flush()
        s.add(SavedLead(lead_id=str(uuid.uuid4()), campaign_id="c1", name="Creator 1", lead_data=LEADS[1]))
        from app.models.discovery_run import RunCandidate
        for i, (stage, why) in enumerate([("shortlisted", None), ("scored", None),
                                          ("filtered_out", "inactive for 140 days"), ("filtered_out", "inactive for 9 days"),
                                          ("filtered_out", "below the view floor for saas (high price)"),
                                          ("judged", "not an individual creator; posts in a different language")]):
            s.add(RunCandidate(run_id="r1", creator_id=f"youtube:UC{i}", platform="youtube", stage=stage, drop_reason=why))
        s.add(RunCandidate(run_id="other", creator_id="youtube:X", platform="youtube", stage="filtered_out", drop_reason="no views"))
        await s.commit()

    async def get_db():
        async with sf() as session:
            yield session

    async def me():
        return {"sub": "clerk-1"}

    auth._USER_CACHE.clear()
    monkeypatch.setattr(auth, "AsyncSessionLocal", sf)
    app.dependency_overrides[database.get_db] = get_db
    app.dependency_overrides[auth.get_current_user] = me
    stats = {"sql": []}
    event.listen(engine.sync_engine, "before_cursor_execute", lambda conn, cur, statement, *a: stats["sql"].append(statement))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        c.stats = stats
        yield c
    app.dependency_overrides.clear()
    auth._USER_CACHE.clear()
    await engine.dispose()


@needs_pg
@pytest.mark.asyncio
async def test_list_counts_leads_in_the_database_without_loading_them(client):
    client.stats["sql"].clear()
    r = await client.get("/api/campaigns/")
    assert r.status_code == 200
    rows = {c["id"]: c for c in r.json()}
    assert set(rows) == {"c1", "c2"}  # only my campaigns
    assert rows["c1"]["leads_count"] == 7 and rows["c2"]["leads_count"] == 0
    assert rows["c2"]["name"] == "Untitled Campaign" and rows["c1"]["status"] == "completed"
    listing = [q for q in client.stats["sql"] if "FROM campaigns" in q]
    assert listing and "jsonb_array_length" in listing[0] and "jsonb_typeof" in listing[0] and "campaigns.campaign_leads," not in listing[0]


@needs_pg
@pytest.mark.asyncio
async def test_leads_response_is_unchanged_and_owner_only(client):
    r = await client.get("/api/campaigns/c1/leads")
    assert r.status_code == 200 and r.headers["content-type"] == "application/json"
    assert r.json() == {"status": "COMPLETED", "current_stage": None, "stage_index": None, "result": LEADS,
                        "campaign_details": {"brand": {"name": "B"}}, "name": "Mine", "error": None}
    empty = (await client.get("/api/campaigns/c2/leads")).json()
    assert empty["result"] is None and empty["status"] == "CREATED"
    assert (await client.get("/api/campaigns/c3/leads")).status_code == 404  # someone else's
    assert (await client.get("/api/campaigns/missing/leads")).status_code == 404


@needs_pg
@pytest.mark.asyncio
async def test_status_and_details_skip_the_results_and_extra_connections(client, monkeypatch):
    import psycopg

    def no_new_connections(*a, **k):
        raise AssertionError("status must not open a separate database connection")
    monkeypatch.setattr(psycopg.AsyncConnection, "connect", no_new_connections)
    client.stats["sql"].clear()
    st = await client.get("/api/campaigns/c1/status")
    assert st.status_code == 200 and st.json()["run_id"] == "r1" and st.json()["thread_id"] == "discovery-r1"
    d = await client.get("/api/campaigns/c1/details")
    assert d.status_code == 200 and d.json()["campaign_details"] == {"brand": {"name": "B"}}
    assert not any("campaign_leads" in q for q in client.stats["sql"])
    assert (await client.get("/api/campaigns/c3/status")).status_code == 404


@needs_pg
@pytest.mark.asyncio
async def test_saved_leads_owner_check_does_not_load_results(client):
    client.stats["sql"].clear()
    r = await client.get("/api/saved/?campaign_id=c1")
    assert r.status_code == 200 and [l["lead_data"]["id"] for l in r.json()] == ["UC1"]
    assert not any("campaign_leads" in q for q in client.stats["sql"])
    assert (await client.get("/api/saved/?campaign_id=c3")).status_code == 404


@pytest.mark.asyncio
async def test_keep_warm_function_is_served_and_does_no_work():
    from types import SimpleNamespace

    from app.inngest import functions as F

    assert F.WARM_CRON == "*/5 * * * *"
    assert await F.keep_backend_warm._handler(SimpleNamespace()) == {"ok": True}


def test_heavy_modules_are_not_loaded_at_startup():
    """Cold start: LangGraph and the outreach graph load only when a run starts."""
    import subprocess, sys, os

    code = ("import sys, app.main; heavy = [m for m in ('langgraph.graph', 'app.outreach.graph', "
            "'langgraph.checkpoint.postgres') if m in sys.modules]; print(heavy)")
    env = {**os.environ, "GOOGLE_API_KEY": "x", "INNGEST_DEV": "1"}
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=os.getcwd())
    assert out.stdout.strip().splitlines()[-1] == "[]", out.stderr[-500:]


@needs_pg
@pytest.mark.asyncio
async def test_skipped_summary_groups_reasons_for_my_run_only(client):
    r = await client.get("/api/campaigns/c1/skipped")
    assert r.status_code == 200
    body = r.json()
    assert body["looked_at"] == 6 and body["skipped"] == 4
    reasons = {x["reason"]: x["count"] for x in body["reasons"]}
    assert reasons == {"inactive": 2, "too few views": 1, "not an individual creator": 1, "different language": 1}
    assert body["reasons"][0] == {"reason": "inactive", "count": 2}  # most common first
    assert (await client.get("/api/campaigns/c2/skipped")).json() == {"looked_at": 0, "skipped": 0, "reasons": []}
    assert (await client.get("/api/campaigns/c3/skipped")).status_code == 404  # someone else's campaign

"""Read endpoints the campaign pages call: same responses as before the speed-ups, owner-only access,
and no hidden extra work (results JSON not loaded for the list; no extra DB connection for /status).
Needs real Postgres (jsonb functions): runs when PG_TEST_URL is set."""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

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
    from app.models.share_link import ShareLink  # noqa: F401
    from app.models.deal import CreatorDeal  # noqa: F401
    from app.models.outreach import OutreachJob  # noqa: F401
    from app.models.saved_lead import SavedLead
    from app.models.user import User
    from tests.discovery.conftest import create_tables, make_engine

    engine, is_pg = make_engine(tmp_path)
    await create_tables(engine, is_pg, ["users", "campaigns", "saved_leads", "run_candidates", "share_links", "share_feedback", "creator_deals", "deal_events", "share_events", "agent_proposals", "connected_accounts", "deal_posts", "tracking_links", "link_clicks", "outreach_jobs", "outreach_pitches", "post_stats", "conversions"])
    sf = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as s:
        s.add_all([User(user_id="u1", clerk_id="clerk-1"), User(user_id="u2", clerk_id="clerk-2")])
        await s.flush()
        s.add_all([
            Campaign(campaign_id="c1", user_id="u1", name="Mine", campaign_details={"brand": {"name": "B"}},
                     campaign_leads=LEADS, status=CampaignStatus.COMPLETED, thread_id="discovery-r1", run_id="r1"),
            Campaign(campaign_id="c2", user_id="u1", name=None, campaign_leads=None, status=CampaignStatus.CREATED),
            Campaign(campaign_id="c3", user_id="u2", name="Theirs", campaign_leads=LEADS, status=CampaignStatus.COMPLETED),
            # a draft left 3 days ago without a brief: hidden from the list
            Campaign(campaign_id="c4", user_id="u1", name="Untitled Campaign", status=CampaignStatus.CREATED,
                     created_at=datetime.now(timezone.utc) - timedelta(days=3)),
            # an older campaign that kept the placeholder name: listed under its brief's name
            Campaign(campaign_id="c5", user_id="u1", name="Untitled Campaign", status=CampaignStatus.PENDING,
                     campaign_details={"brand": {"name": "DataLaunch"}, "campaign": {"goal": "sales"},
                                       "constraints": {"target_countries": ["IN"]}},
                     workflow_status={"status": "running"}, created_at=datetime.now(timezone.utc) - timedelta(days=30)),
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
    assert set(rows) == {"c1", "c2", "c5"}  # only mine, and not the abandoned empty draft (c4)
    assert rows["c5"]["name"] == "DataLaunch · Sales · India" and rows["c5"]["run_status"] == "running"
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


@needs_pg
@pytest.mark.asyncio
async def test_rename_and_delete_are_owner_only_and_delete_cascades(client, monkeypatch):
    r = await client.patch("/api/campaigns/c1", json={"name": "  Launch\n week  "})
    assert r.status_code == 200 and r.json()["name"] == "Launch week"
    assert (await client.patch("/api/campaigns/c1", json={"name": "   "})).status_code == 422
    assert (await client.patch("/api/campaigns/c3", json={"name": "mine now"})).status_code == 404
    assert (await client.delete("/api/campaigns/c3")).status_code == 404  # someone else's
    assert (await client.delete("/api/campaigns/c5")).status_code == 409  # search still running
    assert (await client.delete("/api/campaigns/c1")).status_code == 200
    assert (await client.get("/api/campaigns/c1/leads")).status_code == 404
    assert (await client.get("/api/saved/?campaign_id=c1")).status_code == 404  # its saved creators went too


@needs_pg
@pytest.mark.asyncio
async def test_running_a_campaign_names_it_from_the_brief_unless_the_user_named_it(client, monkeypatch):
    from app.api.routes import campaign as routes

    sent = []

    async def fake_send(event):
        sent.append(event)
    monkeypatch.setattr(routes.inngest_client, "send", fake_send)
    brief = {"brand": {"name": "Acme"}, "campaign": {"goal": "signups"}, "audience": {"locations": ["US", "GB"]}}
    assert (await client.post("/api/campaigns/c2/generate", json=brief)).status_code == 200
    assert (await client.get("/api/campaigns/c2/details")).json()["name"] == "Acme · Signups · United States +1"
    await client.patch("/api/campaigns/c2", json={"name": "My name"})
    await client.post("/api/campaigns/c2/generate", json={**brief, "brand": {"name": "Other"}})
    assert (await client.get("/api/campaigns/c2/details")).json()["name"] == "My name" and len(sent) == 2


def test_name_from_brief():
    from app.api.campaign_names import clean_name, is_default, name_from_brief

    assert name_from_brief({"brand": {"name": "DataLaunch"}, "campaign": {"goal": "sales"},
                            "constraints": {"target_countries": ["AE"]}}) == "DataLaunch · Sales · UAE"
    assert name_from_brief({"brand": {"name": "X"}, "audience": {"locations": ["ZW"]}}) == "X · ZW"  # unknown code
    assert name_from_brief({"brand": {"name": " "}}) is None and name_from_brief(None) is None
    assert is_default(None) and is_default(" Untitled Campaign ") and not is_default("Launch")
    assert len(clean_name("a" * 200)) == 80


# --- share links ------------------------------------------------------------------------------

SECRET_LEAD = {**LEADS[0], "socials": {"email": "me@creator.com", "instagram": "https://instagram.com/c"},
               "valuation": 500, "fair_low": 400, "fair_high": 600, "estimated_cpm": 12,
               "description": "contact me@creator.com", "match_terms": ["brief topic"], "new_private_field": "x"}


@needs_pg
@pytest.mark.asyncio
async def test_share_links_show_only_allowed_fields_and_respect_prices(client):
    from sqlalchemy import update as sa_update

    from app.models.campaign import Campaign

    # put a lead with contacts and prices into c1 (the fixture's session factory is the app's)
    from app.api.routes import share as share_routes  # noqa: F401
    r = await client.post("/api/campaigns/c1/shares", json={"kind": "anyone"})
    assert r.status_code == 200
    link = r.json()
    assert link["path"].startswith("/s/") and link["expires_at"] and link["show_prices"] is False

    async def patch_leads(leads):
        from app.db import database
        gen = client._transport.app.dependency_overrides[database.get_db]()
        db = await gen.__anext__()
        await db.execute(sa_update(Campaign).where(Campaign.campaign_id == "c1").values(campaign_leads=leads))
        await db.commit()
        await gen.aclose()
    await patch_leads([SECRET_LEAD, *LEADS[1:]])

    pub = (await client.get("/api/share/" + link["path"][3:])).json()
    assert pub["campaign_name"] == "Mine" and pub["shared_by"] == "B" and len(pub["creators"]) == 7
    first = pub["creators"][0]
    text = str(pub)
    assert "me@creator.com" not in text and "instagram.com" not in text  # contacts never leave
    assert "new_private_field" not in first and "match_terms" not in first and "description" not in first
    assert first["valuation"] is None and first["estimated_cpm"] is None  # prices off
    assert first["final_score"] == 50.5 and first["title"] == "Creator 0"

    # prices on for this link only
    assert (await client.patch(f"/api/shares/{link['id']}", json={"show_prices": True})).json()["show_prices"]
    first = (await client.get("/api/share/" + link["path"][3:])).json()["creators"][0]
    assert first["valuation"] == 500 and first["fair_high"] == 600

    # a personal link for two creators
    p = (await client.post("/api/campaigns/c1/shares",
                           json={"kind": "person", "email": " Investor@Fund.com ", "creator_ids": ["UC1", "UC2", "nope"]})).json()
    assert p["email"] == "investor@fund.com" and p["creator_ids"] == ["UC1", "UC2"] and p["expires_at"] is None
    shared = (await client.get("/api/share/" + p["path"][3:])).json()
    assert [c["id"] for c in shared["creators"]] == ["UC1", "UC2"]
    # the same person and creators again: the same link
    again = (await client.post("/api/campaigns/c1/shares",
                               json={"kind": "person", "email": "investor@fund.com", "creator_ids": ["UC1", "UC2"]})).json()
    assert again["id"] == p["id"]

    listed = (await client.get("/api/campaigns/c1/shares")).json()["links"]
    assert {l["id"] for l in listed} == {link["id"], p["id"]}
    assert next(l for l in listed if l["id"] == link["id"])["view_count"] == 2

    # revoke: gone at once
    assert (await client.delete(f"/api/shares/{p['id']}")).status_code == 200
    r = await client.get("/api/share/" + p["path"][3:])
    assert r.status_code == 410 and r.headers["cache-control"] == "no-store" and "noindex" in r.headers["x-robots-tag"]
    assert (await client.get("/api/share/not-a-token")).status_code == 404


@needs_pg
@pytest.mark.asyncio
async def test_share_links_are_owner_only_and_validated(client):
    assert (await client.post("/api/campaigns/c3/shares", json={"kind": "anyone"})).status_code == 404  # not mine
    assert (await client.get("/api/campaigns/c3/shares")).status_code == 404
    assert (await client.post("/api/campaigns/c2/shares", json={"kind": "anyone"})).status_code == 422  # no creators yet
    assert (await client.post("/api/campaigns/c1/shares", json={"kind": "person", "email": "nope"})).status_code == 422
    assert (await client.post("/api/campaigns/c1/shares", json={"kind": "anyone", "creator_ids": ["x"]})).status_code == 422
    assert (await client.patch("/api/shares/missing", json={"show_prices": True})).status_code == 404


@needs_pg
@pytest.mark.asyncio
async def test_expired_public_link_stops_working(client):
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import update as sa_update

    from app.db import database
    from app.models.share_link import ShareLink

    link = (await client.post("/api/campaigns/c1/shares", json={"kind": "anyone"})).json()
    gen = client._transport.app.dependency_overrides[database.get_db]()
    db = await gen.__anext__()
    await db.execute(sa_update(ShareLink).where(ShareLink.link_id == link["id"])
                     .values(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
    await db.commit()
    await gen.aclose()
    assert (await client.get("/api/share/" + link["path"][3:])).status_code == 410
    assert (await client.get("/api/campaigns/c1/shares")).json()["links"] == []  # expired links drop off the list


def test_shared_lead_allowlist_without_a_database():
    from types import SimpleNamespace

    from app.sharing.view import ANYONE_LINK_DAYS, anyone_link_expiry, clean_email, new_token, shared_view

    link = SimpleNamespace(creator_ids=None, role="viewer", show_prices=False, expires_at=None)
    v = shared_view("Camp", {"brand": {"name": "Acme"}}, [SECRET_LEAD, "junk", None], link)
    c = v["creators"][0]
    assert len(v["creators"]) == 1 and c["socials"] == {"email": None, "instagram": None, "twitter": None, "linkedin": None}
    assert set(c["metrics"]) <= {"avg_views", "engagement_rate", "reliability", "trust_score", "forecast", "volatility",
                                 "raw_engagement"}
    assert clean_email("A@B.co ") == "a@b.co" and clean_email("a@b") is None
    assert len(new_token()) >= 32 and new_token() != new_token()
    from datetime import datetime, timezone
    assert (anyone_link_expiry(datetime(2026, 1, 1, tzinfo=timezone.utc)) - datetime(2026, 1, 1, tzinfo=timezone.utc)).days == ANYONE_LINK_DAYS



# --- reviewers and contacts (F1.18b) -----------------------------------------------------------

async def _set_leads(client, leads):
    from sqlalchemy import update as sa_update

    from app.db import database
    from app.models.campaign import Campaign

    gen = client._transport.app.dependency_overrides[database.get_db]()
    db = await gen.__anext__()
    await db.execute(sa_update(Campaign).where(Campaign.campaign_id == "c1").values(campaign_leads=leads))
    await db.commit()
    await gen.aclose()


@needs_pg
@pytest.mark.asyncio
async def test_reviewers_give_feedback_the_owner_sees(client):
    assert (await client.post("/api/campaigns/c1/shares", json={"kind": "anyone", "role": "reviewer"})).status_code == 422
    r = (await client.post("/api/campaigns/c1/shares", json={"kind": "person", "email": "cofounder@x.com", "role": "reviewer",
                                                            "creator_ids": ["UC1", "UC2"]})).json()
    assert r["role"] == "reviewer"
    tok = r["path"][3:]
    pub = (await client.get(f"/api/share/{tok}")).json()
    assert pub["can_review"] is True and pub["my_feedback"] == {}
    ok = await client.put(f"/api/share/{tok}/feedback/UC1", json={"verdict": "yes", "comment": "  Great fit  "})
    assert ok.status_code == 200 and ok.json() == {"creator_id": "UC1", "verdict": "yes", "comment": "Great fit"}
    await client.put(f"/api/share/{tok}/feedback/UC1", json={"verdict": "no", "comment": None})  # latest wins
    assert (await client.put(f"/api/share/{tok}/feedback/UC5", json={"verdict": "yes"})).status_code == 404  # not shared
    assert (await client.put(f"/api/share/{tok}/feedback/UC1", json={"verdict": "maybe"})).status_code == 422
    assert (await client.get(f"/api/share/{tok}")).json()["my_feedback"] == {"UC1": {"verdict": "no", "comment": None}}

    viewer = (await client.post("/api/campaigns/c1/shares", json={"kind": "person", "email": "inv@x.com"})).json()
    assert (await client.put(f"/api/share/{viewer['path'][3:]}/feedback/UC1", json={"verdict": "yes"})).status_code == 403
    assert (await client.get(f"/api/share/{viewer['path'][3:]}")).json()["can_review"] is False

    fb = (await client.get("/api/campaigns/c1/feedback")).json()
    assert fb == [{"creator_id": "UC1", "by": "cofounder@x.com", "verdict": "no", "comment": None, "updated_at": fb[0]["updated_at"]}]
    assert (await client.get("/api/campaigns/c3/feedback")).status_code == 404  # not my campaign
    # removing the reviewer's link keeps what they said, but they can't add more
    await client.delete(f"/api/shares/{r['id']}")
    assert len((await client.get("/api/campaigns/c1/feedback")).json()) == 1
    assert (await client.put(f"/api/share/{tok}/feedback/UC2", json={"verdict": "yes"})).status_code == 410


@needs_pg
@pytest.mark.asyncio
async def test_links_never_share_contacts_even_if_asked(client):
    await _set_leads(client, [SECRET_LEAD, *LEADS[1:]])
    link = (await client.post("/api/campaigns/c1/shares", json={"kind": "person", "email": "va@x.com", "show_contacts": True,
                                                               "role": "reviewer", "show_prices": True})).json()
    assert "show_contacts" not in link
    page = (await client.get("/api/share/" + link["path"][3:])).json()
    assert "me@creator.com" not in str(page) and "instagram.com" not in str(page) and "contacts" not in page
    assert (await client.post("/api/share/" + link["path"][3:] + "/code")).status_code in (404, 405)  # no code step


# --- deals (F7.1) ---------------------------------------------------------------------------------

DEAL_LEADS = [{**l, "fair_low": 150, "fair_high": 210, "metrics": {"avg_views": 28300, "forecast": "~424 clicks/video"}}
              for l in LEADS]


@needs_pg
@pytest.mark.asyncio
async def test_deals_board_flow(client):
    await _set_leads(client, DEAL_LEADS)
    assert (await client.post("/api/campaigns/c1/deals", json={"creator_ids": ["nope"]})).status_code == 422
    r = (await client.post("/api/campaigns/c1/deals", json={"creator_ids": ["UC1", "UC2", "UC1", "x"]})).json()
    assert [d["creator_id"] for d in r["created"]] == ["UC1", "UC2"] and r["skipped"] == 0
    again = (await client.post("/api/campaigns/c1/deals", json={"creator_ids": ["UC1", "UC3"]})).json()
    assert [d["creator_id"] for d in again["created"]] == ["UC3"] and again["skipped"] == 1  # UC1 already in deals
    d = r["created"][0]
    assert d["stage"] == "contacted" and d["name"] == "Creator 1" and d["typical_views"] == 28300
    assert d["advice"]["fair_low"] == 150 and d["advice"]["verdict"] is None

    # quote above fair → counter advice; terms change the fair range
    ch = (await client.patch(f"/api/deals/{d['id']}", json={"stage": "negotiating", "quoted_rate": 300})).json()
    assert ch["advice"]["verdict"] == "counter" and ch["advice"]["counter"] == 180
    ch = (await client.patch(f"/api/deals/{d['id']}", json={"deliverable": "dedicated", "usage_rights": "paid_90"})).json()
    assert ch["advice"]["verdict"] in ("accept", "great")

    # validation
    for bad in ({"stage": "won"}, {"deliverable": "tweetstorm"}, {"quoted_rate": -5}, {"commission_pct": 150},
                {"exclusivity_days": 999}, {"post_url": "https://evil.com/watch?v=1"}, {"post_url": "javascript:alert(1)"}):
        assert (await client.patch(f"/api/deals/{d['id']}", json=bad)).status_code == 422, bad

    # agreed → live → paid: dates and amounts filled in, all on the timeline
    await client.patch(f"/api/deals/{d['id']}", json={"stage": "agreed", "agreed_rate": 400, "post_by": "2020-01-01"})
    board = (await client.get("/api/campaigns/c1/deals")).json()
    me = next(x for x in board["deals"] if x["id"] == d["id"])
    assert me["overdue"] is True and board["summary"]["committed"] == 400 and board["summary"]["agreed"] == 1
    live = (await client.patch(f"/api/deals/{d['id']}", json={"stage": "live", "post_url": " https://www.youtube.com/watch?v=abc "})).json()
    assert live["live_at"] and live["post_url"] == "https://www.youtube.com/watch?v=abc" and live["overdue"] is False
    paid = (await client.patch(f"/api/deals/{d['id']}", json={"stage": "paid"})).json()
    assert paid["paid_at"] and paid["paid_amount"] == 400
    s = (await client.get("/api/campaigns/c1/deals")).json()["summary"]
    assert s["paid"] == 400 and s["live"] == 1 and s["by_stage"]["paid"] == 1
    types = [e["type"] for e in (await client.get(f"/api/deals/{d['id']}/events")).json()]
    assert types.count("stage") == 4 and "created" in types and "quoted_rate" in types and "agreed_rate" in types

    # lost deals don't count; delete works; someone else's campaign is invisible
    await client.patch(f"/api/deals/{r['created'][1]['id']}", json={"stage": "lost"})
    assert (await client.get("/api/campaigns/c1/deals")).json()["summary"]["deals"] == 2
    assert (await client.delete(f"/api/deals/{r['created'][1]['id']}")).status_code == 200
    assert (await client.get("/api/campaigns/c3/deals")).status_code == 404
    assert (await client.post("/api/campaigns/c3/deals", json={"creator_ids": ["UC1"]})).status_code == 404


@needs_pg
@pytest.mark.asyncio
async def test_typed_ask_in_words_goes_through_the_agent(client, monkeypatch):
    """"7 + 20% commision" is $7 + 20%, never $720; the suggestion carries the agent's reasons."""
    from app.judge import client as jc
    from app.judge.client import Answer, Judgment
    from app.llm import client as llm

    await _set_leads(client, DEAL_LEADS)
    d = (await client.post("/api/campaigns/c1/deals", json={"creator_ids": ["UC3"]})).json()["created"][0]

    async def judge(state, questions, context=None, **k):
        if "move" not in questions:
            return Judgment({q: Answer("noul", 0.05 if q == "extra_promise" else 0.9) for q in questions}, "jev", "jev")
        picks = {"their_fee": "f0", "their_commission": "p0", "move": "accept", "structure": "fee_plus_commission",
                 "commission": "20", "extra": "none"}
        return Judgment({q: Answer("choice", picks[q]) if q in picks else Answer("score", 1) if q == "concession"
                         else Answer("noul", 0.05) for q in questions}, "jev", "jev")

    async def write(route, messages, **k):
        return "Hi there! $7 plus 20% commission works for us. Shall we lock in the details?"
    monkeypatch.setattr(jc, "judge", judge)
    monkeypatch.setattr(llm, "achat", write)

    r = (await client.post(f"/api/deals/{d['id']}/reply", json={"text": "7 + 20% commision"})).json()
    assert r["deal"]["quoted_rate"] == 7 and r["deal"]["quoted_commission_pct"] == 20 and r["deal"]["stage"] == "negotiating"
    [p] = r["proposals"]
    assert p["kind"] == "agree" and p["title"] == "Agree to $7 + 20% commission" and "They asked $7 + 20% commission." in p["reason"]
    a = (await client.post(f"/api/proposals/{p['id']}/approve", json={})).json()
    assert a["deal"]["stage"] == "agreed" and a["deal"]["agreed_rate"] == 7 and a["deal"]["commission_pct"] == 20
    assert a["deal"]["deal_type"] == "base_plus_commission"


@needs_pg
@pytest.mark.asyncio
async def test_no_fair_price_then_set_one_and_suggest_again(client, monkeypatch):
    from app.judge import client as jc
    from app.judge.client import Answer, Judgment
    from app.llm import client as llm

    await _set_leads(client, LEADS)  # no fair price in these results
    d = (await client.post("/api/campaigns/c1/deals", json={"creator_ids": ["UC2"]})).json()["created"][0]

    async def judge(state, questions, context=None, **k):
        if "move" not in questions:
            return Judgment({q: Answer("noul", 0.05 if q == "extra_promise" else 0.9) for q in questions}, "jev", "jev")
        picks = {"their_fee": "f0", "their_commission": "p0", "move": "counter", "structure": "fee_plus_commission",
                 "commission": "10", "extra": "none"}
        return Judgment({q: Answer("choice", picks[q]) if q in picks else Answer("score", 1) if q == "concession"
                         else Answer("noul", 0.05) for q in questions}, "jev", "jev")

    async def write(route, messages, **k):
        text = messages[1].content
        return "Hi there, could we do $10 plus 10% commission on sales? Would that work?" if "$10 + 10%" in text else "x"
    monkeypatch.setattr(jc, "judge", judge)
    monkeypatch.setattr(llm, "achat", write)

    r = (await client.post(f"/api/deals/{d['id']}/reply", json={"text": "i need 20 dollars and 10% commission"})).json()
    assert r["agent"]["action"] == "none" and "no fair price" in r["agent"]["reasons"][0] and r["proposals"] == []
    assert r["deal"]["quoted_rate"] == 20  # what they asked is still read and saved

    assert (await client.patch(f"/api/deals/{d['id']}", json={"fair_low": 30, "fair_high": 10})).status_code == 422
    await client.patch(f"/api/deals/{d['id']}", json={"fair_low": 8, "fair_high": 12})
    again = (await client.post(f"/api/deals/{d['id']}/negotiate")).json()
    [p] = again["proposals"]
    assert p["kind"] == "send_counter" and p["title"].startswith("Offer: $") and "10% commission" in p["title"]


@needs_pg
@pytest.mark.asyncio
async def test_own_message_in_the_chat_and_last_message_preview(client):
    await _set_leads(client, DEAL_LEADS)
    d = (await client.post("/api/campaigns/c1/deals", json={"creator_ids": ["UC4"]})).json()["created"][0]
    assert (await client.post(f"/api/deals/{d['id']}/message", json={"text": "  "})).status_code == 422
    r = (await client.post(f"/api/deals/{d['id']}/message", json={"text": "Hey!  Loved your   last video."})).json()
    assert r["sent"] is False  # no Gmail connected: recorded as sent, the founder copies it
    me = next(x for x in (await client.get("/api/campaigns/c1/deals")).json()["deals"] if x["id"] == d["id"])
    assert me["last_message"]["who"] == "you" and me["last_message"]["text"] == "Hey! Loved your last video."
    events = (await client.get(f"/api/deals/{d['id']}/events")).json()
    assert events[0]["type"] == "message_sent" and events[0]["payload"]["kind"] == "manual"


@needs_pg
@pytest.mark.asyncio
async def test_gmail_connect_send_and_replies_flow(client, monkeypatch):
    """Connect Gmail → send the first pitch → their reply comes in → approve the counter → it's sent in the thread."""
    import base64
    from urllib.parse import parse_qs, urlparse

    from sqlalchemy import select as sa_select

    from app.db import database
    from app.gmail import client as GC
    from app.judge import client as jc
    from app.judge.client import Answer, Judgment
    from app.models.deal import ConnectedAccount

    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "cid.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-secret")
    await _set_leads(client, [{**l, "socials": {"email": "creator@x.io"}} for l in DEAL_LEADS])

    assert (await client.get("/api/gmail")).json()["connected"] is False
    url = (await client.post("/api/gmail/connect", json={"return_to": "/campaign/c1/deals"})).json()["url"]
    q = parse_qs(urlparse(url).query)
    assert q["client_id"] == ["cid.apps.googleusercontent.com"] and "gmail.send" in q["scope"][0] and q["access_type"] == ["offline"]

    async def exchange(code, redirect_uri):
        assert code == "abc" and redirect_uri.endswith("/api/gmail/callback")
        return {"access_token": "at", "refresh_token": "rt-secret", "scope": " ".join(GC.G.SCOPES)}
    sent = []

    async def send(token, raw, thread_id=None):
        sent.append((base64.urlsafe_b64decode(raw).decode(), thread_id))
        return {"id": f"g{len(sent)}", "threadId": "t1"}

    async def message(token, mid):
        return {"payload": {"headers": [{"name": "Message-ID", "value": f"<{mid}@mail.gmail.com>"}]}}

    reply_data = base64.urlsafe_b64encode(b"Hi! My rate is $300 for a segment.\n\nOn Mon, X wrote:\n> earlier").decode()

    async def thread(token, tid):
        return {"messages": [
            {"id": "g1", "labelIds": ["SENT"], "payload": {"headers": [{"name": "From", "value": "me@gmail.com"},
                                                                     {"name": "Message-ID", "value": "<g1@mail.gmail.com>"}]}},
            {"id": "r1", "labelIds": ["INBOX"], "payload": {"mimeType": "text/plain", "body": {"data": reply_data},
                                                          "headers": [{"name": "From", "value": "Creator <creator@x.io>"},
                                                                      {"name": "Message-ID", "value": "<r1@x.io>"}]}}]}

    async def judge(state, questions, context=None, **k):
        if "move" not in questions:  # the draft check
            return Judgment({q: Answer("noul", 0.05 if q == "extra_promise" else 0.9) for q in questions}, "jev", "jev")
        assert "earlier" not in state["reply"]["text"]  # quoted history stripped
        picks = {"their_fee": "f0", "their_commission": "none", "move": "counter", "structure": "flat", "commission": "0",
                 "extra": "none"}
        return Judgment({q: Answer("choice", picks[q]) if q in picks else Answer("score", 1) if q == "concession"
                         else Answer("noul", 0.05) for q in questions}, "jev", "jev")

    async def write(route, messages, **k):
        return "Hi there, thanks for your rate. Could we do $165 for a sponsored segment? Would that work?"
    from app.llm import client as llm
    monkeypatch.setattr(llm, "achat", write)

    for name, fn in (("exchange_code", exchange), ("send", send), ("message", message), ("thread", thread)):
        monkeypatch.setattr(GC, name, fn)
    monkeypatch.setattr(GC, "profile", lambda token: _async({"emailAddress": "Me@gmail.com"}))
    monkeypatch.setattr(GC, "access_token", lambda rt: _async("at"))
    monkeypatch.setattr(GC, "display_name", lambda token: _async("Srijan Patel"))
    monkeypatch.setattr(jc, "judge", judge)

    bad = await client.get("/api/gmail/callback", params={"state": "forged.x", "code": "abc"}, follow_redirects=False)
    assert bad.status_code == 302 and "gmail=expired" in bad.headers["location"]
    r = await client.get("/api/gmail/callback", params={"state": q["state"][0], "code": "abc"}, follow_redirects=False)
    assert r.headers["location"] == "/campaign/c1/deals?gmail=connected"
    st = (await client.get("/api/gmail")).json()
    assert st["connected"] and st["email"] == "me@gmail.com"
    gen = client._transport.app.dependency_overrides[database.get_db]()
    db = await gen.__anext__()
    stored = (await db.execute(sa_select(ConnectedAccount))).scalar_one()
    assert "rt-secret" not in stored.refresh_token  # encrypted at rest
    await gen.aclose()

    # first pitch from Outreach: creates the deal and the thread
    out = (await client.post("/api/campaigns/c1/outreach/send", json={"creator_id": "UC1", "subject": "Collab?", "body": "Hi, want to work together?"})).json()
    d = out["deal"]
    assert d["stage"] == "contacted" and d["contact_email"] == "creator@x.io" and d["emailing"] is True
    assert "To: creator@x.io" in sent[0][0] and "Subject: Collab?" in sent[0][0] and sent[0][1] is None
    assert "From: Srijan Patel <me@gmail.com>" in sent[0][0]  # a real sender name, not a bare address
    again = await client.post("/api/campaigns/c1/outreach/send", json={"creator_id": "UC1", "subject": "x", "body": "y"})
    assert again.status_code == 409

    # their reply comes in; Jev reads it once; the next step is to write down the quote
    assert (await client.post("/api/campaigns/c1/gmail/sync", params={"force": True})).json()["new"] == 1
    assert (await client.post("/api/campaigns/c1/gmail/sync", params={"force": True})).json()["new"] == 0
    board = (await client.get("/api/campaigns/c1/deals")).json()
    [c] = board["proposals"]
    assert board["deals"][0]["quoted_rate"] == 300 and board["deals"][0]["stage"] == "negotiating"
    assert c["kind"] == "send_counter" and c["can_send"] is True and c["title"] == "Offer: $165"

    a = (await client.post(f"/api/proposals/{c['id']}/approve", json={})).json()
    assert a["sent"] is True and len(sent) == 2
    body, tid = sent[1]
    assert tid == "t1" and "Subject: Re: Collab?" in body and "In-Reply-To: <r1@x.io>" in body and "$165" in body

    # copy instead of sending, and disconnecting
    assert (await client.delete("/api/gmail")).json()["connected"] is False
    assert (await client.post("/api/campaigns/c1/outreach/send", json={"creator_id": "UC2", "subject": "a", "body": "b"})).status_code == 409


async def _async(v):
    return v


@needs_pg
@pytest.mark.asyncio
async def test_share_activity_feeds_the_sharing_panel(client):
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import update as sa_update

    from app.db import database
    from app.models.share_link import ShareLink

    rev = (await client.post("/api/campaigns/c1/shares", json={"kind": "person", "email": "co@x.io", "role": "reviewer",
                                                              "creator_ids": ["UC1", "UC2", "UC3"]})).json()
    pub = (await client.post("/api/campaigns/c1/shares", json={"kind": "anyone"})).json()
    tok = rev["path"][3:]
    await client.get(f"/api/share/{tok}")
    await client.get(f"/api/share/{tok}")  # within 30 minutes: one "opened" event
    await client.get(f"/api/share/{pub['path'][3:]}")
    await client.put(f"/api/share/{tok}/feedback/UC1", json={"verdict": "yes", "comment": "great fit"})
    await client.put(f"/api/share/{tok}/feedback/UC2", json={"verdict": "no"})
    await client.put(f"/api/share/{tok}/feedback/UC1", json={"verdict": "yes", "comment": "great fit, ask for rates"})

    a = (await client.get("/api/campaigns/c1/share-activity")).json()
    types = [(e["type"], e["by"]) for e in a["events"]]
    assert types.count(("opened", "co@x.io")) == 1 and ("opened", "Someone with the public link") in types
    assert [e for e in a["events"] if e["type"] == "feedback"][0]["comment"] == "great fit, ask for rates"  # newest first
    assert a["latest_at"] == a["events"][0]["at"]
    me = next(p for p in a["people"] if p["email"] == "co@x.io")
    assert me["view_count"] == 2 and me["reviewed"] == 2 and me["yes"] == 1 and me["no"] == 1 and me["creators"] == 3
    rows = {r["creator_id"]: r for r in a["by_creator"]}
    assert rows["UC1"]["yes"] == 1 and rows["UC1"]["name"] == "Creator 1" and rows["UC1"]["notes"][0]["by"] == "co@x.io"
    assert rows["UC2"]["no"] == 1 and a["by_creator"][0]["creator_id"] == "UC1"  # most approved first

    # an open after 30 minutes is a new event
    gen = client._transport.app.dependency_overrides[database.get_db]()
    db = await gen.__anext__()
    await db.execute(sa_update(ShareLink).where(ShareLink.link_id == rev["id"])
                     .values(last_viewed_at=datetime.now(timezone.utc) - timedelta(hours=1)))
    await db.commit()
    await gen.aclose()
    await client.get(f"/api/share/{tok}")
    a2 = (await client.get("/api/campaigns/c1/share-activity")).json()
    assert [(e["type"], e["by"]) for e in a2["events"]].count(("opened", "co@x.io")) == 2
    # removed people leave the People list but their activity stays
    await client.delete(f"/api/shares/{rev['id']}")
    a3 = (await client.get("/api/campaigns/c1/share-activity")).json()
    assert all(p["email"] != "co@x.io" for p in a3["people"]) and any(e["by"] == "co@x.io" for e in a3["events"])
    assert (await client.get("/api/campaigns/c3/share-activity")).status_code == 404


@needs_pg
@pytest.mark.asyncio
async def test_asking_more_after_agreeing_is_flagged_and_chats_track_unread(client, monkeypatch):
    """After agreeing $12, "they ask for extra 10$" is a change request to $22: the deal stays agreed, the
    agent drafts a reply holding $12, and the founder can accept $22 instead. Pasting the same reply twice
    is refused. Replies are unread until the chat is opened; the inbox lists them across campaigns."""
    from app.judge import client as jc
    from app.judge.client import Answer, Judgment
    from app.llm import client as llm

    await _set_leads(client, [{**l, "fair_low": 9, "fair_high": 15} for l in DEAL_LEADS])
    d = (await client.post("/api/campaigns/c1/deals", json={"creator_ids": ["UC1"]})).json()["created"][0]
    await client.patch(f"/api/deals/{d['id']}", json={"stage": "agreed", "agreed_rate": 12})
    await client.post(f"/api/deals/{d['id']}/read")

    async def judge(state, questions, context=None, **k):
        if "move" not in questions:
            return Judgment({q: Answer("noul", 0.05 if q == "extra_promise" else 0.9) for q in questions}, "jev", "jev")
        assert state["deal"]["current_price"] == "$12" and state["deal"]["already_agreed"] is True
        picks = {"their_fee": "f0", "their_commission": "none", "move": "counter", "structure": "flat", "commission": "0", "extra": "none"}
        return Judgment({q: Answer("choice", picks[q]) if q in picks else Answer("score", 1) if q == "concession"
                         else Answer("noul", 0.9 if q == "ask_is_extra" else 0.05) for q in questions}, "jev", "jev")

    async def write(route, messages, **k):
        return "Hi there, thanks! We agreed $12 and that's what we budgeted, so we'd love to keep it. Excited for the post!"
    monkeypatch.setattr(jc, "judge", judge)
    monkeypatch.setattr(llm, "achat", write)

    r = (await client.post(f"/api/deals/{d['id']}/reply", json={"text": "they ask for extra 10$"})).json()
    assert r["deal"]["stage"] == "agreed" and r["deal"]["agreed_rate"] == 12 and r["deal"]["quoted_rate"] is None
    [p] = r["proposals"]
    assert p["kind"] == "hold_terms" and p["is_message"] and "$12" in p["message"]
    assert p["change"] == {"from": {"fee": 12, "commission_pct": 0.0}, "to": {"fee": 22, "commission_pct": 0.0}}
    assert (await client.post(f"/api/deals/{d['id']}/reply", json={"text": "They ask for  EXTRA 10$"})).status_code == 409

    deals = (await client.get("/api/campaigns/c1/deals")).json()["deals"]
    assert deals[0]["unread"] == 1
    box = (await client.get("/api/inbox")).json()
    assert box["unread"] == 1 and box["items"][0]["deal_id"] == d["id"] and box["items"][0]["draft"] is True
    assert box["by_campaign"]["c1"]["unread"] == 1
    await client.post(f"/api/deals/{d['id']}/read")
    assert (await client.get("/api/campaigns/c1/deals")).json()["deals"][0]["unread"] == 0

    a = (await client.post(f"/api/proposals/{p['id']}/accept-change")).json()
    assert a["deal"]["agreed_rate"] == 22 and a["deal"]["stage"] == "agreed" and a["proposals"] == []
    assert (await client.get("/api/inbox")).json()["items"] == []


@needs_pg
@pytest.mark.asyncio
async def test_pitches_land_in_chats_then_agree_sets_up_posts_link_and_code(client):
    """Writing pitches creates each creator's chat; the first message arrives as a draft per channel; switching
    to a DM copies instead of sending; agreeing saves the posts, makes a link and code, and drafts the confirmation."""
    from app.db import database
    from app.models.outreach import OutreachJob
    from app.outreach.drafts import drafts_from_job

    await _set_leads(client, [{**l, "socials": {"instagram": "https://instagram.com/c1"}} for l in DEAL_LEADS])
    job = (await client.post("/api/outreach/campaigns/c1/jobs", json={"selected_creator_ids": ["UC1", "UC2"], "auto_start": False})).json()
    board = (await client.get("/api/campaigns/c1/deals")).json()
    assert {d["creator_id"] for d in board["deals"]} == {"UC1", "UC2"} and board["deals"][0]["channel"] == "instagram"

    gen = client._transport.app.dependency_overrides[database.get_db]()
    db = await gen.__anext__()
    j = await db.get(OutreachJob, job["outreach_job_id"])
    bundle = {"pitch_angle": "Their M4 review", "email": {"subject": "Your M4 review", "body": "Hi there, loved the review."},
              "instagram": {"body": "Loved the M4 review!"}}
    assert await drafts_from_job(db, j, {"UC1": {"pitch_bundle": bundle}, "UC2": {"pitch_bundle": {}}}, {}) == 1
    await db.commit()
    await gen.aclose()

    board = (await client.get("/api/campaigns/c1/deals")).json()
    [p] = [p for p in board["proposals"] if p["kind"] == "pitch"]
    d1 = next(d for d in board["deals"] if d["creator_id"] == "UC1")
    assert p["deal_id"] == d1["id"] and p["message"] == "Loved the M4 review!" and p["subject"] == "Your M4 review"
    assert p["texts"]["email"]["body"] == "Hi there, loved the review." and p["can_send"] is False and p["seen"] is False
    await client.post(f"/api/proposals/{p['id']}/seen")
    assert (await client.post(f"/api/campaigns/c1/pitches/send", json={})).status_code == 409  # no Gmail connected

    assert (await client.patch(f"/api/deals/{d1['id']}", json={"channel": "fax"})).status_code == 422
    sent = (await client.post(f"/api/proposals/{p['id']}/approve", json={"message": "Loved the M4 review!", "via": "copy"})).json()
    assert sent["sent"] is False
    ev = (await client.get(f"/api/deals/{d1['id']}/events")).json()
    assert ev[0]["type"] == "message_sent" and ev[0]["payload"]["kind"] == "pitch"

    # agree: two posts, paid when live, link to the founder's site
    bad = await client.post(f"/api/deals/{d1['id']}/agree", json={"fee": 12, "posts": []})
    assert bad.status_code == 422
    r = (await client.post(f"/api/deals/{d1['id']}/agree", json={
        "fee": 12, "pay_when": "on_live", "link_to": "acme.com",
        "posts": [{"deliverable": "integration", "due_on": "2026-11-20"}, {"deliverable": "short", "due_on": "2026-11-25"}]})).json()
    deal = r["deal"]
    assert deal["stage"] == "agreed" and deal["agreed_rate"] == 12 and deal["post_by"] == "2026-11-20" and deal["pay_when"] == "on_live"
    assert [p["deliverable"] for p in deal["posts"]] == ["integration", "short"] and deal["tracking_code"].startswith("CREATOR")
    link = deal["link"]
    assert link["target"] == "https://acme.com" and link["url"].endswith(f"/r/{link['slug']}") and link["clicks"] == 0
    [c] = [p for p in r["proposals"] if p["kind"] == "confirm_terms"]
    assert "1 sponsored segment by Nov 20" in c["message"] and "1 short by Nov 25" in c["message"]
    assert deal["tracking_code"] in c["message"] and link["slug"] in c["message"] and "$12, paid when the post is live" in c["message"]

    # the link counts people, not bots; unknown links 404
    assert (await client.get(f"/api/links/{link['slug']}")).json()["url"] == f"https://acme.com?ref={deal['tracking_code']}"
    await client.get(f"/api/links/{link['slug']}", headers={"user-agent": "Twitterbot/1.0"})
    assert (await client.get(f"/api/links/nope")).status_code == 404
    again = next(d for d in (await client.get("/api/campaigns/c1/deals")).json()["deals"] if d["id"] == d1["id"])
    assert again["link"]["clicks"] == 1


@needs_pg
@pytest.mark.asyncio
async def test_track_finds_posts_counts_results_and_records_payments(client, monkeypatch):
    """Agree → the daily check finds the post by its code, fetches views, reads comments after 3 days → Track
    totals, verdicts and To pay; signups from the site snippet and a store CSV; Mark paid; the results CSV."""
    from datetime import datetime, timedelta, timezone

    from app.db import database
    from app.judge import client as jc
    from app.judge.client import Answer, Judgment
    from app.tracking.find import refresh_campaign

    await _set_leads(client, DEAL_LEADS)
    d = (await client.post("/api/campaigns/c1/deals", json={"creator_ids": ["UC1"]})).json()["created"][0]
    agreed = (await client.post(f"/api/deals/{d['id']}/agree", json={
        "fee": 100, "pay_when": "on_live", "link_to": "acme.com", "posts": [{"deliverable": "integration", "due_on": "2026-11-20"}]})).json()["deal"]
    code = agreed["tracking_code"]
    published = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat().replace("+00:00", "Z")

    class FakeYT:
        calls: list = []

        async def playlist_items(self, **p):
            self.calls.append(("uploads", p["playlistId"]))
            return {"items": [
                {"snippet": {"title": "My week vlog", "description": "no sponsor", "publishedAt": published}, "contentDetails": {"videoId": "AAAAAAAAAAA", "videoPublishedAt": published}},
                {"snippet": {"title": "Best laptop setup", "description": f"Use code {code.lower()} for 10% off", "publishedAt": published,
                             "thumbnails": {"medium": {"url": "https://i.ytimg.com/x.jpg"}}},
                 "contentDetails": {"videoId": "BBBBBBBBBBB", "videoPublishedAt": published}}]}

        async def videos(self, **p):
            return {"items": [{"id": "BBBBBBBBBBB", "statistics": {"viewCount": "5000", "likeCount": "300", "commentCount": "40"}}]}

        async def comment_threads(self, **p):
            return {"items": [{"snippet": {"topLevelComment": {"snippet": {"textDisplay": t, "likeCount": n}}}}
                              for t, n in (("Where can I get this?", 50), ("great video", 10))]}

    asked = []

    async def judge(state, questions, context=None, **k):
        asked.append(set(questions))
        if "is_sponsored_post" in questions:
            return Judgment({"is_sponsored_post": Answer("noul", 0.1)}, "jev", "jev")
        return Judgment({"sentiment": Answer("score", 3), "product_interest": Answer("noul", 0.9),
                         "product_questions": Answer("noul", 0.8), "ad_backlash": Answer("noul", 0.1)}, "jev", "jev")
    monkeypatch.setattr(jc, "judge", judge)

    gen = client._transport.app.dependency_overrides[database.get_db]()
    db = await gen.__anext__()
    assert (await refresh_campaign(db, "c1", FakeYT(), user_id="u1"))["found"] == 1
    assert (await refresh_campaign(db, "c1", FakeYT(), user_id="u1")).get("skipped")  # not again within minutes
    assert {"sentiment", "product_interest", "product_questions", "ad_backlash"} not in asked  # too new to read comments
    from sqlalchemy import update as sa_update

    from app.models.deal import DealPost
    await db.execute(sa_update(DealPost).values(live_at=datetime.now(timezone.utc) - timedelta(days=4)))
    await db.commit()
    await refresh_campaign(db, "c1", FakeYT(), user_id="u1", force=True)
    await gen.aclose()
    assert {"is_sponsored_post"} not in asked  # the code matched for free; Jev only read the comments

    # results: snippet signup (by code), a store CSV, a manual count, a click
    t = (await client.get("/api/campaigns/c1/track")).json()
    key = t["snippet"]["key"]
    assert t["posts"][0]["video_id"] == "BBBBBBBBBBB" and t["posts"][0]["found_by"] == "code" and t["posts"][0]["state"] == "live"
    summary = t["posts"][0]["comment_summary"]
    assert summary["sentiment"] == "Mostly positive" and summary["product_interest"] and not summary["ad_backlash"]
    assert summary["top"][0] == "Where can I get this?"
    for body in (json.dumps({"ref": code.lower()}), json.dumps({"ref": "NOPE"}), "garbage"):
        assert (await client.post(f"/api/t/{key}", content=body, headers={"content-type": "text/plain"})).status_code == 204
    r = (await client.post("/api/campaigns/c1/conversions/csv", json={"text": f"code,uses\n{code},3\nOTHER,9\n", "kind": "code_use"})).json()
    assert r == {"added": 3, "unknown_codes": ["OTHER"]}
    assert (await client.post(f"/api/deals/{d['id']}/conversions", json={"kind": "signup", "count": 4})).status_code == 200
    await client.get(f"/api/links/{agreed['link']['slug']}")
    await client.patch("/api/campaigns/c1/track", json={"goal_kind": "signups", "goal_count": 100, "value_each": 20})
    assert (await client.patch("/api/campaigns/c1/track", json={"goal_kind": "followers"})).status_code == 422

    t = (await client.get("/api/campaigns/c1/track")).json()
    tot = t["totals"]
    assert tot["views"] == 5000 and tot["clicks"] == 1 and tot["results"] == 5 and tot["code_uses"] == 3
    assert tot["cost_per_result"] == 20 and tot["value"] == 100 and tot["return"] == 1.0
    assert t["goal"] == {"kind": "signups", "count": 100, "value_each": 20}
    assert t["forecast"]["estimate"] and t["forecast"]["views"] > 5000
    assert t["creators"][0]["verdict"] in ("rebook", "ok", "skip") and t["to_pay"] == [
        {"deal_id": d["id"], "name": "Creator 1", "avatar_url": None, "amount": 100.0, "why": "Post is live"}]

    # pay, then the CSV
    assert (await client.post(f"/api/deals/{d['id']}/paid", json={"amount": 100, "method": "cash"})).status_code == 422
    await client.post(f"/api/deals/{d['id']}/paid", json={"amount": 100, "method": "paypal", "paid_on": "2026-11-25", "note": "INV-1"})
    t = (await client.get("/api/campaigns/c1/track")).json()
    assert t["to_pay"] == [] and t["paid"][0]["method"] == "paypal" and t["totals"]["paid"] == 100
    csv_text = (await client.get("/api/campaigns/c1/track.csv")).text
    assert csv_text.splitlines()[0].startswith("Creator,Price,Posts") and "Creator 1,100.0,1,https://www.youtube.com/watch?v=BBBBBBBBBBB,5000,1,5,3,5" in csv_text
    assert "paypal" in csv_text and "2026-11-25" in csv_text
    assert (await client.get("/api/campaigns/c3/track")).status_code == 404

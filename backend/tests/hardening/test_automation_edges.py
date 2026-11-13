"""Automations under stress, with Gmail, Jev and the LLM simulated (no live calls): a message can never be
sent twice, one failure never stops the others, an AI outage never loses a creator's reply, and a pitch the
model got wrong is never sent by "Send all". Needs real Postgres (PG_TEST_URL)."""

import asyncio
import os

import httpx
import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

needs_pg = pytest.mark.skipif(not os.getenv("PG_TEST_URL"), reason="needs PG_TEST_URL (real Postgres)")
pytestmark = [needs_pg, pytest.mark.asyncio]

TABLES = ["users", "campaigns", "saved_leads", "run_candidates", "share_links", "share_feedback", "creator_deals",
          "deal_events", "share_events", "agent_proposals", "connected_accounts", "deal_posts", "tracking_links",
          "link_clicks", "outreach_jobs", "outreach_pitches", "post_stats", "conversions", "credit_ledger",
          "credit_reservations", "subscriptions", "payments", "billing_events"]
LEADS = [{"id": f"UC{i}", "title": f"Creator {i}", "socials": {"email": f"c{i}@example.com"}} for i in range(4)]
PITCH = "Hi Creator,\n\nLoved your recent video.\n\nWould you be open to a collaboration with Lumen?"


@pytest_asyncio.fixture
async def env(tmp_path, monkeypatch):
    from app.auth import user as auth
    from app.db import database
    from app.main import app
    from app.models import discovery_run, outreach, saved_lead, share_link  # noqa: F401  (register tables)
    from app.models.campaign import Campaign, CampaignStatus
    from app.models.deal import AgentProposal, ConnectedAccount, CreatorDeal
    from app.models.user import User
    from tests.discovery.conftest import create_tables, make_engine

    engine, is_pg = make_engine(tmp_path)
    await create_tables(engine, is_pg, TABLES)
    sf = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as s:
        s.add(User(user_id="u1", clerk_id="clerk-1"))
        await s.flush()
        s.add(Campaign(campaign_id="c1", user_id="u1", name="Test", campaign_details={"brand": {"name": "Lumen"}},
                       campaign_leads=LEADS, status=CampaignStatus.COMPLETED))
        s.add(ConnectedAccount(user_id="u1", email="me@example.com", refresh_token="x", status="active"))
        await s.flush()
        for i in range(4):
            s.add(CreatorDeal(deal_id=f"d{i}", campaign_id="c1", creator_id=f"UC{i}", creator_name=f"Creator {i}",
                              contact_email=f"c{i}@example.com", fair_low=150, fair_high=210))
        await s.flush()
        for i in range(4):
            s.add(AgentProposal(proposal_id=f"p{i}", campaign_id="c1", deal_id=f"d{i}", key="pitch:j1", kind="pitch",
                                status="pending", title="First message",
                                payload={"message": PITCH, "subject": "Your video", "seen": True,
                                         "needs_review": i == 3, "problems": ["pitch mentions money"] if i == 3 else []}))
        await s.commit()

    sends: list[str] = []
    fail: dict = {}

    async def fake_send(db, account, d, text, subject=None):
        await asyncio.sleep(0.05)  # a real send takes a moment: wide enough for a race to show
        if d.deal_id in fail:
            raise fail[d.deal_id]
        sends.append(d.deal_id)
        d.gmail_thread_id = f"t-{d.deal_id}"
        return {"gmail_id": f"g-{d.deal_id}-{len(sends)}", "thread_id": d.gmail_thread_id}

    monkeypatch.setattr("app.gmail.service.send_for_deal", fake_send)

    async def get_db():
        async with sf() as session:
            yield session

    async def me():
        return {"sub": "clerk-1"}

    auth._USER_CACHE.clear()
    monkeypatch.setattr(auth, "AsyncSessionLocal", sf)
    app.dependency_overrides[database.get_db] = get_db
    app.dependency_overrides[auth.get_current_user] = me
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        c.sf, c.sends, c.fail = sf, sends, fail
        yield c
    app.dependency_overrides.clear()
    auth._USER_CACHE.clear()
    await engine.dispose()


async def _status(sf, pid):
    from app.models.deal import AgentProposal

    async with sf() as s:
        return (await s.execute(select(AgentProposal.status).where(AgentProposal.proposal_id == pid))).scalar_one()


async def _events(sf, deal_id, kind):
    from app.models.deal import DealEvent

    async with sf() as s:
        return list((await s.execute(select(DealEvent).where(DealEvent.deal_id == deal_id, DealEvent.type == kind))).scalars())


async def test_a_double_click_sends_the_email_once(env):
    r1, r2, r3 = await asyncio.gather(*(env.post("/api/proposals/p0/approve", json={}) for _ in range(3)))
    codes = sorted([r1.status_code, r2.status_code, r3.status_code])
    assert codes == [200, 409, 409], codes
    assert env.sends == ["d0"]
    assert len(await _events(env.sf, "d0", "message_sent")) == 1
    assert await _status(env.sf, "p0") == "approved"


async def test_send_all_and_a_single_approve_at_the_same_time_send_once(env):
    a, b = await asyncio.gather(env.post("/api/campaigns/c1/pitches/send", json={}),
                                env.post("/api/proposals/p1/approve", json={}))
    assert a.status_code == 200 and b.status_code in (200, 409)
    assert sorted(env.sends) == ["d0", "d1", "d2"]  # each once; p3 needs review
    for d in ("d0", "d1", "d2"):
        assert len(await _events(env.sf, d, "message_sent")) == 1


async def test_send_all_carries_on_after_failures_and_leaves_them_to_retry(env):
    env.fail["d1"] = HTTPException(502, "Gmail had a hiccup")
    env.fail["d2"] = RuntimeError("socket closed")
    r = await env.post("/api/campaigns/c1/pitches/send", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sent"] == 1 and env.sends == ["d0"]
    whys = {s["name"]: s["why"] for s in body["skipped"]}
    assert whys["Creator 1"] == "Gmail had a hiccup"
    assert whys["Creator 2"] == "Couldn't send it just now: try again"
    assert "has problems" in whys["Creator 3"]  # the flagged draft is never sent in bulk
    assert await _status(env.sf, "p1") == "pending" and await _status(env.sf, "p2") == "pending"
    assert await _status(env.sf, "p3") == "pending"
    # once Gmail is back, the same button sends the two that failed
    env.fail.clear()
    r = await env.post("/api/campaigns/c1/pitches/send", json={})
    assert r.json()["sent"] == 2 and sorted(env.sends) == ["d0", "d1", "d2"]


async def test_a_failed_single_send_can_be_tried_again(env):
    env.fail["d0"] = HTTPException(502, "Gmail had a hiccup")
    r = await env.post("/api/proposals/p0/approve", json={})
    assert r.status_code == 502 and await _status(env.sf, "p0") == "pending"
    assert await _events(env.sf, "d0", "message_sent") == []
    env.fail.clear()
    r = await env.post("/api/proposals/p0/approve", json={})
    assert r.status_code == 200 and env.sends == ["d0"]


async def test_flagged_draft_shows_its_problems(env):
    r = await env.get("/api/campaigns/c1/deals")
    p3 = next(p for p in r.json()["proposals"] if p["id"] == "p3")
    assert p3["needs_review"] is True and p3["problems"] == ["pitch mentions money"]


async def test_an_ai_outage_never_loses_a_pasted_reply(env, monkeypatch):
    async def down(state):
        raise RuntimeError("Jev timed out")

    monkeypatch.setattr("app.negotiation.graph.run", down)
    r = await env.post("/api/deals/d0/reply", json={"text": "My rate is $400 for a video."})
    assert r.status_code == 200, r.text
    assert r.json()["agent"]["action"] == "none"
    assert "couldn't read this reply" in r.json()["agent"]["reasons"][0]
    [reply] = await _events(env.sf, "d0", "creator_reply")
    assert reply.payload["text"] == "My rate is $400 for a video." and reply.payload["agent"]["error"] is True


async def test_gmail_sync_keeps_going_when_one_thread_breaks(env, monkeypatch):
    from app.gmail import client as GC
    from app.gmail import service as GS
    from app.models.deal import ConnectedAccount, CreatorDeal

    async with env.sf() as s:
        for i in (0, 1):
            d = await s.get(CreatorDeal, f"d{i}")
            d.gmail_thread_id = f"t{i}"
        await s.commit()

    async def token(refresh):
        return "tok"

    def msg(i):
        return {"id": f"m{i}", "labelIds": ["INBOX"], "payload": {"headers": [
            {"name": "From", "value": f"c{i}@example.com"}, {"name": "Message-ID", "value": f"<m{i}@x>"}],
            "mimeType": "text/plain", "body": {"data": ""}}, "snippet": f"Sounds good, my rate is ${100 + i}"}

    async def thread(tok, tid):
        if tid == "t0":
            raise ValueError("unexpected Gmail payload")  # a thread we can't parse
        return {"messages": [msg(1)]}

    calls = []

    async def fake_negotiate(db, d, reply, **k):
        calls.append(d.deal_id)
        return {"action": "none", "reasons": []}

    monkeypatch.setattr(GC, "access_token", token)
    monkeypatch.setattr(GC, "thread", thread)
    monkeypatch.setattr("app.gmail.mail.reply_text", lambda m: m.get("snippet"))
    monkeypatch.setattr("app.negotiation.run.negotiate", fake_negotiate)
    monkeypatch.setattr("app.gmail.crypto.decrypt", lambda v: "refresh")
    async with env.sf() as s:
        account = (await s.execute(select(ConnectedAccount))).scalar_one()
        deals = list((await s.execute(select(CreatorDeal))).scalars())
        new = await GS.sync_deals(s, account, deals, user_id="u1", force=True)
    assert new == 1 and calls == ["d1"]
    assert len(await _events(env.sf, "d1", "creator_reply")) == 1


async def test_one_creators_pitch_failing_does_not_fail_the_batch(monkeypatch):
    from app.outreach.graph import build_outreach_graph
    from app.schemas.outreach import PitchBundle

    async def fake_achat(route, prompt, schema, context=None):
        if '"name": "Creator 1"' in prompt:
            raise RuntimeError("every model failed")
        cid = "UC0"
        return PitchBundle.model_validate({
            "creator_id": cid, "pitch_angle": "x",
            "personalization": [{"evidence_id": "video_1", "reason": "r"}],
            "email": {"subject": "Your launch video", "body": "Hi Creator,\n\nLoved your launch video.\n\nWould you be open to a collaboration with Lumen?"},
        })

    import sys

    import app.outreach.graph  # noqa: F401  (loads the node modules)

    # the nodes package re-exports functions named like their modules: patch the modules themselves
    monkeypatch.setattr(sys.modules["app.outreach.nodes.generate_creator_pitch"], "achat", fake_achat)
    monkeypatch.setattr(sys.modules["app.outreach.nodes.repair_creator_pitch"], "achat", fake_achat)
    creators = [{"id": f"UC{i}", "title": f"Creator {i}", "socials": {"email": "x@y.z"},
                 "recent_videos": [{"title": "Launch video"}]} for i in range(2)]
    out = await build_outreach_graph().compile().ainvoke({
        "outreach_job_id": "j1", "campaign_id": "c1", "campaign_context": {"brand": {"name": "Lumen"}},
        "selected_creators": creators, "default_collaboration": {"type": "partnership"}})
    by_id = {r["creator_id"]: r for r in out["pitch_results"]}
    assert by_id["UC0"]["status"] == "completed"
    assert by_id["UC1"]["status"] == "failed" and "couldn't write this pitch" in by_id["UC1"]["validation_errors"][0]
    assert out["generation_stats"]["successful_count"] == 1


async def test_slim_loaders_keep_every_field_the_pages_use(env):
    """The Deals page and chat actions read creators cut down in SQL: same values as the stored ones."""
    from app.api.routes import deals as R
    from app.models.campaign import Campaign
    from app.models.user import User

    full = {"id": "UC0", "title": "Creator 0", "socials": {"email": "c0@example.com"}, "signals": {"sponsored_posts": 2},
            "metrics": {"avg_views": 5000}, "subscribers": 12000, "avatar_url": "https://img/a.jpg",
            "posts": [{"text": "big"}] * 5, "description": "long " * 200}
    async with env.sf() as s:
        c = await s.get(Campaign, "c1")
        c.campaign_leads = [full] + LEADS[1:]
        await s.commit()
    async with env.sf() as s:
        user = (await s.execute(select(User))).scalar_one()
        camp = await R._campaign_slim(s, "c1", user)
        d, row = await R._deal(s, "d0", user)
        for leads in (camp.campaign_leads, row.campaign_leads):
            lead = R._leads_by_id(leads)["UC0"]
            assert "posts" not in lead and "description" not in lead
            for k in ("title", "socials", "signals", "metrics", "subscribers", "avatar_url"):
                assert lead[k] == full[k]
    r = await env.get("/api/inbox")
    assert r.status_code == 200
    names = {i["deal_id"]: i["name"] for i in r.json()["items"]}
    assert names["d0"] == "Creator 0" and names["d1"] == "Creator 1"

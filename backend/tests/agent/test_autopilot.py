"""Autopilot (decided Nov 14): what goes out by itself, when, and what waits for the founder. Gmail, Jev and the
model are simulated. The database parts need real Postgres (PG_TEST_URL), like the other queue tests."""

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from app.agent import autopilot as AP
from app.agent import constants as A

NOW = datetime(2026, 11, 16, 10, 0, tzinfo=timezone.utc)  # a Monday, 10:00 UTC
SINCE = NOW - timedelta(hours=1)


# --- pure rules (no database) ------------------------------------------------------------------------

def P(kind="pitch", created=NOW, **payload):
    return SimpleNamespace(kind=kind, created_at=created, proposal_id=f"p-{kind}-{created.isoformat()}",
                           payload={"message": "Hi", **payload})


ON = AP.Settings(True, False, SINCE)


def test_what_goes_out_by_itself():
    assert AP.hold_reason(P(), None, {}, ON, email_route=True) is None
    assert AP.hold_reason(P("send_counter"), None, {}, ON, email_route=True) is None
    assert AP.hold_reason(P("follow_up"), None, {}, ON, email_route=True) is None
    # decisions are always the founder's
    assert AP.hold_reason(P("agree"), None, {}, ON, email_route=True) == "manual"
    assert AP.hold_reason(P("mark_lost"), None, {}, ON, email_route=True) == "manual"
    # off, or drafted before autopilot was switched on
    assert AP.hold_reason(P(), None, {}, AP.Settings(False, False, SINCE), email_route=True) == "manual"
    assert AP.hold_reason(P(created=SINCE - timedelta(minutes=1)), None, {}, ON, email_route=True) == "manual"


def test_what_waits_for_the_founder():
    assert AP.hold_reason(P(), None, {}, AP.Settings(True, True, SINCE), email_route=True) == "review_first"
    assert AP.hold_reason(P(needs_review=True), None, {}, ON, email_route=True) == "needs_review"
    assert AP.hold_reason(P(), None, {"contact": {"contacted_before": "2026-11-01"}}, ON, email_route=True) == "contacted_before"
    assert AP.hold_reason(P("send_counter", held="question"), None, {}, ON, email_route=True) == "question"
    assert AP.hold_reason(P("send_counter", held="needs_human"), None, {}, ON, email_route=True) == "needs_human"
    assert AP.hold_reason(P(), None, {}, ON, email_route=False) == "no_email"
    assert AP.hold_reason(P(auto_failures=2), None, {}, ON, email_route=True) == "failed"
    # "check first emails" doesn't hold replies
    assert AP.hold_reason(P("send_counter"), None, {}, AP.Settings(True, True, SINCE), email_route=True) is None


def test_pacing():
    # replies: ~10 minutes after the creator wrote
    assert AP.due_at(P("send_counter"), {}, now=NOW, last_first=None) == NOW + timedelta(minutes=10)
    # new conversations: 2-6 minutes after the last one
    gap = AP.due_at(P(), {}, now=NOW, last_first=NOW) - NOW
    assert timedelta(minutes=2) <= gap <= timedelta(minutes=6)
    # in the creator's daytime: 10:00 UTC is 15:30 in India (ok), 05:00 in New York (wait until 08:00)
    assert AP.due_at(P(), {"country": "IN"}, now=NOW, last_first=None) == NOW
    ny = AP.due_at(P(), {"country": "US"}, now=NOW, last_first=None)
    assert ny == datetime(2026, 11, 16, 13, 0, tzinfo=timezone.utc)  # 08:00 EST
    late = datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)  # 20:30 in India: tomorrow 08:00
    assert AP.daytime(late, "IN") == datetime(2026, 11, 17, 2, 30, tzinfo=timezone.utc)
    assert AP.daytime(late, None) == late


def test_switching_on_only_covers_new_drafts():
    first = AP.turned_on(None, autopilot=True, review_first=False, now=NOW)
    assert first["since"] == NOW.isoformat()
    later = AP.turned_on(first, autopilot=True, review_first=True, now=NOW + timedelta(days=1))
    assert later["since"] == NOW.isoformat() and later["review_first"]  # still on: same start
    off = AP.turned_on(later, autopilot=False, review_first=True, now=NOW + timedelta(days=2))
    back = AP.turned_on(off, autopilot=True, review_first=False, now=NOW + timedelta(days=3))
    assert back["since"] == (NOW + timedelta(days=3)).isoformat()  # back on: drafts from the off time stay manual


def test_notices():
    assert AP.notice("agree", "Priya", {"terms": {"fee": 300, "commission_pct": 10}}) == "Priya accepted $300 + 10% commission. Agree to lock it in."
    assert "bounced" in AP.notice("mark_lost", "Priya", {"bounced": True})
    assert "asked not to be contacted" in AP.notice("mark_lost", "Priya", {"opt_out": True})
    assert AP.notice("pitch", "Priya", {"held": "needs_review"}).startswith("Priya: The draft")
    assert AP.notice("pitch", "Priya", {"held": "review_first"}) is None  # the founder chose that: no email about it
    assert AP.notice("send_counter", "Priya", {}) is None


def test_bounces_are_recognised():
    from app.gmail.mail import is_bounce

    def msg(frm, subject):
        return {"payload": {"headers": [{"name": "From", "value": frm}, {"name": "Subject", "value": subject}]}}
    assert is_bounce(msg("Mail Delivery Subsystem <mailer-daemon@googlemail.com>", "Delivery Status Notification (Failure)"))
    assert is_bounce(msg("postmaster@outlook.com", "Undeliverable: Hi"))
    assert not is_bounce(msg("Priya <priya@hey.com>", "Re: Your video"))


def test_replies_that_need_the_founder_are_held():
    from app.negotiation.run import _held

    assert _held({"needs_human": 0.9}, {"source": "ai", "check": {"answers": 0.9}}) == "needs_human"
    assert _held({"asks_question": 0.9}, {"source": "ai", "check": {"answers": 0.4}}) == "question"
    assert _held({"asks_question": 0.9}, {"source": "template"}) == "question"
    assert _held({"asks_question": 0.9}, {"source": "ai", "check": {"answers": 0.85}}) is None  # the draft answers it
    assert _held({"asks_question": 0.1, "needs_human": 0.1}, {}) is None


# --- with a database ---------------------------------------------------------------------------------

# the database stamps sent messages with its own clock, so these tests run on real time (country-free leads)
DB_NOW = datetime.now(timezone.utc)
DB_SINCE = DB_NOW - timedelta(hours=1)
needs_pg = pytest.mark.skipif(not os.getenv("PG_TEST_URL"), reason="needs PG_TEST_URL (real Postgres)")
TABLES = ["users", "campaigns", "saved_leads", "run_candidates", "share_links", "share_feedback", "creator_deals",
          "deal_events", "share_events", "agent_proposals", "connected_accounts", "deal_posts", "tracking_links",
          "link_clicks", "outreach_jobs", "outreach_pitches", "post_stats", "conversions", "contact_history",
          "suppression_list"]


@pytest_asyncio.fixture
async def sf(tmp_path):
    from app.models import contact, discovery_run, outreach, saved_lead, share_link  # noqa: F401  (register tables)
    from app.models.campaign import Campaign, CampaignStatus
    from app.models.deal import AgentProposal, ConnectedAccount, CreatorDeal
    from app.models.user import User
    from tests.discovery.conftest import create_tables, make_engine

    engine, is_pg = make_engine(tmp_path)
    await create_tables(engine, is_pg, TABLES)
    f = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    leads = [{"id": f"UC{i}", "title": f"Creator {i}"} for i in range(6)]
    leads[5]["contact"] = {"contacted_before": "2026-11-01T00:00:00+00:00"}
    async with f() as s:
        s.add(User(user_id="u1", clerk_id="k1"))
        await s.flush()
        s.add(Campaign(campaign_id="c1", user_id="u1", name="T", campaign_details={"brand": {"name": "Lumen"}},
                       campaign_leads=leads, status=CampaignStatus.COMPLETED,
                       outreach_settings={"autopilot": True, "review_first": False, "since": DB_SINCE.isoformat()}))
        s.add(ConnectedAccount(user_id="u1", email="me@lumen.io", refresh_token="x", status="active"))
        await s.flush()
        for i in range(6):
            s.add(CreatorDeal(deal_id=f"d{i}", campaign_id="c1", creator_id=f"UC{i}", creator_name=f"Creator {i}",
                              contact_email=f"c{i}@mail.io", fair_low=150, fair_high=210, stage="contacted",
                              gmail_thread_id="t3" if i == 3 else None))
        await s.flush()
        rows = [("p0", "d0", "pitch", DB_NOW - timedelta(minutes=30), {"subject": "Your desk video"}),
                ("p1", "d1", "pitch", DB_NOW - timedelta(minutes=20), {}),
                ("p2", "d2", "pitch", DB_NOW - timedelta(minutes=20), {"needs_review": True}),
                ("p3", "d3", "send_counter", DB_NOW - timedelta(minutes=2), {"terms": {"fee": 180}}),
                ("p4", "d4", "agree", DB_NOW - timedelta(minutes=5), {"terms": {"fee": 200}}),
                ("p5", "d5", "pitch", DB_NOW - timedelta(minutes=20), {})]
        for pid, did, kind, at, extra in rows:
            s.add(AgentProposal(proposal_id=pid, campaign_id="c1", deal_id=did, key=f"pitch:{pid}" if kind == "pitch" else f"nego:{pid}",
                                kind=kind, status="pending", title=kind, payload={"message": f"Hi from {pid}", **extra}, created_at=at))
        await s.commit()
    yield f
    await engine.dispose()


def fake_gmail(sent: list, fail: dict | None = None):
    async def send(db, account, d, text, subject=None):
        if fail and d.deal_id in fail:
            raise fail[d.deal_id]
        sent.append((d.deal_id, text, subject))
        d.gmail_thread_id = d.gmail_thread_id or f"t-{d.deal_id}"
        return {"gmail_id": f"g{len(sent)}", "thread_id": d.gmail_thread_id}
    return send


@needs_pg
@pytest.mark.asyncio
async def test_sends_one_at_a_time_and_holds_the_rest(sf):
    from app.models.deal import AgentProposal, DealEvent

    sent: list = []
    send = fake_gmail(sent)
    async with sf() as db:
        r = await AP.send_next(db, "u1", now=DB_NOW, send=send)
    assert r["sent"] == "pitch" and sent[0][0] == "d0" and sent[0][2] == "Your desk video"
    async with sf() as db:
        r = await AP.send_next(db, "u1", now=DB_NOW, send=send)  # the next first email waits 2-6 minutes
    assert r["sent"] is None and 120 <= r["wait"] <= 360
    async with sf() as db:
        r = await AP.send_next(db, "u1", now=DB_NOW + timedelta(minutes=7), send=send)
    assert r["sent"] == "pitch" and sent[-1][0] == "d1"
    async with sf() as db:
        r = await AP.send_next(db, "u1", now=DB_NOW + timedelta(minutes=9), send=send)
    assert r["sent"] == "send_counter" and sent[-1][0] == "d3"  # 10+ minutes after the reply came in
    async with sf() as db:
        r = await AP.send_next(db, "u1", now=DB_NOW + timedelta(minutes=20), send=send)
    assert r["sent"] is None and r["wait"] is None  # nothing left for autopilot
    assert [x[0] for x in sent] == ["d0", "d1", "d3"]
    async with sf() as db:
        rows = {p.proposal_id: p for p in (await db.execute(select(AgentProposal))).scalars()}
        assert rows["p2"].status == "pending" and rows["p2"].payload["held"] == "needs_review"
        assert rows["p5"].status == "pending" and rows["p5"].payload["held"] == "contacted_before"
        assert rows["p4"].status == "pending" and "held" not in rows["p4"].payload  # agreeing: the founder's click
        auto = [e for e in (await db.execute(select(DealEvent).where(DealEvent.type == "message_sent"))).scalars()]
        assert len(auto) == 3 and all(e.payload.get("auto") and e.payload["via"] == "gmail" for e in auto)


@needs_pg
@pytest.mark.asyncio
async def test_check_first_emails_and_switching_off(sf):
    from app.models.campaign import Campaign

    sent: list = []
    async with sf() as db:
        c = await db.get(Campaign, "c1")
        c.outreach_settings = {**c.outreach_settings, "review_first": True}
        await db.commit()
    async with sf() as db:
        r = await AP.send_next(db, "u1", now=DB_NOW + timedelta(minutes=15), send=fake_gmail(sent))
    assert r["sent"] == "send_counter" and [x[0] for x in sent] == ["d3"]  # replies still go; first emails wait
    async with sf() as db:
        c = await db.get(Campaign, "c1")
        c.outreach_settings = {**c.outreach_settings, "autopilot": False}
        await db.commit()
    async with sf() as db:
        r = await AP.send_next(db, "u1", now=DB_NOW + timedelta(minutes=30), send=fake_gmail(sent))
    assert r == {"sent": None, "wait": None, "why": "off"}


@needs_pg
@pytest.mark.asyncio
async def test_failures_and_the_daily_cap(sf):
    from app.models.deal import AgentProposal

    sent: list = []
    boom = {"d0": RuntimeError("gmail 500")}
    for _ in range(2):
        async with sf() as db:
            r = await AP.send_next(db, "u1", now=DB_NOW, send=fake_gmail(sent, boom))
        assert r["why"] == "failed" and r["wait"] == 30
    async with sf() as db:
        p0 = await db.get(AgentProposal, "p0")
        assert p0.status == "pending" and p0.payload["auto_failures"] == 2  # given back, never lost
    async with sf() as db:
        r = await AP.send_next(db, "u1", now=DB_NOW, send=fake_gmail(sent, boom))
    assert r["sent"] == "pitch" and sent[-1][0] == "d1"  # the failing one now waits for the founder
    async with sf() as db:
        assert (await db.get(AgentProposal, "p0")).payload["held"] == "failed"
    cap = {"d3": HTTPException(429, "daily limit")}
    async with sf() as db:
        r = await AP.send_next(db, "u1", now=DB_NOW + timedelta(minutes=12), send=fake_gmail(sent, cap))
    assert r == {"sent": None, "wait": None, "why": "daily_cap"}
    async with sf() as db:
        assert (await db.get(AgentProposal, "p3")).status == "pending"


@needs_pg
@pytest.mark.asyncio
async def test_founder_is_told_once(sf):
    mails: list = []

    async def send_mail(to, subject, body):
        mails.append((to, subject, body))

    async with sf() as db:
        await AP.send_next(db, "u1", now=DB_NOW, send=fake_gmail([]))  # marks the held ones
        n = await AP.notify(db, "u1", send_mail=send_mail)
    assert n == 3 and mails[0][0] == "me@lumen.io" and "3 creators need you" in mails[0][1]
    body = mails[0][2]
    assert "Creator 4 accepted $200" in body and "Creator 2: The draft" in body and "Creator 5: You wrote" in body
    assert "/campaign/c1/outreach" in body
    async with sf() as db:
        assert await AP.notify(db, "u1", send_mail=send_mail) == 0 and len(mails) == 1


@needs_pg
@pytest.mark.asyncio
async def test_founder_sending_first_wins(sf):
    """The founder sends a draft from the chat while autopilot is about to: it goes out once."""
    from app.agent import queue as Q
    from app.models.deal import AgentProposal

    async with sf() as db:
        p0 = await db.get(AgentProposal, "p0")
        assert await Q.claim(db, p0)  # the founder's click
    sent: list = []
    async with sf() as db:
        r = await AP.send_next(db, "u1", now=DB_NOW, send=fake_gmail(sent))
    assert r["sent"] == "pitch" and [x[0] for x in sent] == ["d1"]  # autopilot moved on to the next one

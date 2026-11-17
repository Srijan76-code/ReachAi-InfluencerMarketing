"""Permissions the founder gives their agent (F9.8, 8b): asked by the agent, approved once in the browser, scoped, shorter or
stricter at the founder's choice, ended on time or on demand; plus what they unlock in send_message."""

from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.agent import constants as A
from app.agent import grants
from app.agent.autopilot import settings_of
from app.models.agent_grant import AgentGrant
from app.models.campaign import Campaign
from app.models.deal import AgentProposal, CreatorDeal
from tests.mcp.conftest import call_tool, make_key
from tests.mcp.test_send import TEXT, confirm, gmail, preview, sent_events  # noqa: F401  (the fake Gmail fixture)

pytestmark = pytest.mark.asyncio


async def ask(client, token, **kw):
    return await call_tool(client, token, "request_permission", **{"campaign_id": "c1", "ability": "write_replies", **kw})


async def settings(db):
    async with db() as s:
        camp = (await s.execute(select(Campaign).where(Campaign.campaign_id == "c1"))).scalar_one()
        return settings_of(camp.outreach_settings), dict(camp.outreach_settings or {})


async def approve(db, code, **kw):
    async with db() as s:
        return await grants.decide(s, "u1", code, True, **kw)


# --- asking -------------------------------------------------------------------------------------------------

async def test_the_agent_gets_a_link_and_nothing_changes_until_the_founder_approves(client, db):
    out = await ask(client, await make_key(db), ability="send_replies", client_name="Claude Code")
    d = out["structuredContent"]
    assert d["approval_url"].endswith(f"/grant?code={d['user_code']}") and "from your Gmail" in d["what_it_allows"]
    assert (await settings(db))[0].writer == "reachai" and (await settings(db))[0].agent_send is False
    async with db() as s:
        g = (await s.execute(select(AgentGrant))).scalar_one()
    assert g.status == "pending" and g.client_name == "Claude Code" and g.per_day == A.AGENT_SENDS_PER_DAY


async def test_requests_are_checked(client, db):
    token = await make_key(db)
    assert (await ask(client, token, campaign_id="other"))["isError"] is True  # someone else's campaign
    bad = await ask(client, token, ability="write_replies", mode="unattended")
    assert bad["isError"] is True and "unattended" in bad["content"][0]["text"]  # only sending can be unattended
    clamped = await ask(client, token, ability="send_replies", per_day=20)
    assert clamped["isError"] is False
    async with db() as s:
        assert (await s.execute(select(AgentGrant.per_day))).scalar_one() == A.AGENT_SENDS_PER_DAY  # never above the global limit


async def test_my_permissions_lists_what_is_waiting_and_what_is_allowed(client, db):
    token = await make_key(db)
    assert (await call_tool(client, token, "my_permissions"))["structuredContent"]["permissions"] == []
    d = (await ask(client, token))["structuredContent"]
    waiting = (await call_tool(client, token, "my_permissions"))["structuredContent"]["permissions"]
    assert waiting[0]["status"] == "pending" and waiting[0]["user_code"] == d["user_code"]
    await approve(db, d["user_code"])
    allowed = (await call_tool(client, token, "my_permissions"))["structuredContent"]["permissions"]
    assert allowed[0]["status"] == "approved" and allowed[0]["valid_until"]


# --- approving, and what it switches on -------------------------------------------------------------------

async def test_approving_write_replies_turns_on_my_agent_writes_and_ending_it_turns_it_off(client, db):
    d = (await ask(client, await make_key(db)))["structuredContent"]
    await approve(db, d["user_code"])
    assert (await settings(db))[0].writer == "agent"
    async with db() as s:
        g = (await s.execute(select(AgentGrant))).scalar_one()
        await grants.revoke(s, "u1", g.grant_id)
    assert (await settings(db))[0].writer == "reachai"


async def test_a_grant_never_undoes_what_the_founder_set_themselves(client, db):
    async with db() as s:
        camp = (await s.execute(select(Campaign).where(Campaign.campaign_id == "c1"))).scalar_one()
        camp.outreach_settings = {"writer": "agent"}  # the founder switched it on in the app
        await s.commit()
    d = (await ask(client, await make_key(db)))["structuredContent"]
    await approve(db, d["user_code"])
    async with db() as s:
        await grants.revoke(s, "u1", (await s.execute(select(AgentGrant.grant_id))).scalar_one())
    assert (await settings(db))[0].writer == "agent"


async def test_the_founder_can_shorten_and_tighten_but_not_widen(client, db):
    token = await make_key(db)
    d = (await ask(client, token, ability="send_replies", mode="unattended", days=14, per_day=8))["structuredContent"]
    out = await approve(db, d["user_code"], days=30, per_day=100, mode=None)
    async with db() as s:
        g = (await s.execute(select(AgentGrant))).scalar_one()
    assert g.requested_days == 14 and g.per_day == 8 and g.mode == "unattended"  # asking for more changed nothing
    d2 = (await ask(client, token, ability="send_replies", mode="unattended", days=14, per_day=8))["structuredContent"]
    await approve(db, d2["user_code"], days=2, per_day=3, mode="ask")
    async with db() as s:
        g2 = (await s.execute(select(AgentGrant).where(AgentGrant.user_code == d2["user_code"]))).scalar_one()
    assert g2.requested_days == 2 and g2.per_day == 3 and g2.mode == "ask"


async def test_sending_switches_on_with_its_mode_and_limit_and_stops_with_the_grant(client, db):
    d = (await ask(client, await make_key(db), ability="send_replies", mode="unattended", per_day=4))["structuredContent"]
    await approve(db, d["user_code"])
    s, raw = await settings(db)
    assert s.writer == "agent" and s.agent_send and s.agent_send_mode == "unattended" and s.agent_send_per_day == 4
    assert s.agent_send_grant
    async with db() as sess:
        await grants.revoke(sess, "u1", s.agent_send_grant)
    after, _ = await settings(db)
    assert after.agent_send is False and after.writer == "reachai"


async def test_a_denied_or_expired_request_does_nothing(client, db):
    token = await make_key(db)
    a = (await ask(client, token))["structuredContent"]
    async with db() as s:
        await grants.decide(s, "u1", a["user_code"], False)
    b = (await ask(client, token))["structuredContent"]
    async with db() as s:
        await s.execute(AgentGrant.__table__.update().where(AgentGrant.user_code == b["user_code"]).values(
            request_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
        await s.commit()
    from fastapi import HTTPException

    for code in (a["user_code"], b["user_code"]):
        async with db() as s:
            with pytest.raises(HTTPException):
                await grants.decide(s, "u1", code, True)
    assert (await settings(db))[0].writer == "reachai"


async def test_grants_end_on_time(client, db):
    d = (await ask(client, await make_key(db), ability="send_replies"))["structuredContent"]
    await approve(db, d["user_code"])
    async with db() as s:
        assert await grants.expire_due(s, datetime.now(timezone.utc) + timedelta(days=1)) == 0  # not yet
        g = (await s.execute(select(AgentGrant))).scalar_one()
        assert grants.is_active(g) and not grants.is_active(g, datetime.now(timezone.utc) + timedelta(days=60))
        assert await grants.expire_due(s, datetime.now(timezone.utc) + timedelta(days=60)) == 1
    assert (await settings(db))[0].agent_send is False


# --- what grants unlock in send_message ---------------------------------------------------------------------------

async def _deal(db, *, kind="send_counter", source="agent", payload=None):
    async with db() as s:
        s.add(CreatorDeal(deal_id="d_a", campaign_id="c1", creator_id="UC_a", creator_name="Krish Naik", stage="negotiating",
                          contact_email="krish@example.com", channel="email", gmail_thread_id="t0" if kind != "pitch" else None))
        await s.flush()
        s.add(AgentProposal(proposal_id="p1", campaign_id="c1", deal_id="d_a", key="k1", kind=kind, status="pending", title="x",
                            payload={"message": TEXT, "source": source, "terms": {"fee": 180, "commission_pct": 0}, **(payload or {})}))
        await s.commit()


async def _grant_send(client, db, ability="send_replies", **kw):
    d = (await ask(client, await make_key(db), ability=ability, **kw))["structuredContent"]
    await approve(db, d["user_code"])


async def test_an_ask_grant_says_to_ask_and_an_unattended_grant_says_it_may_confirm(client, db, gmail):
    await _deal(db)
    await _grant_send(client, db, mode="ask")
    token = await make_key(db)
    p = (await preview(client, token))["structuredContent"]
    assert p["mode"] == "ask" and p["permission_ends"] and "ask if you should send it" in (await preview(client, token))["content"][0]["text"]
    async with db() as s:
        g = (await s.execute(select(AgentGrant))).scalar_one()
        g.mode = "unattended"
        camp = (await s.execute(select(Campaign).where(Campaign.campaign_id == "c1"))).scalar_one()
        camp.outreach_settings = {**camp.outreach_settings, "agent_send_mode": "unattended"}
        await s.commit()
    out = await preview(client, token)
    assert out["structuredContent"]["mode"] == "unattended" and "you may confirm now" in out["content"][0]["text"]
    sent = await confirm(client, token, out["structuredContent"]["preview_token"])
    assert sent["structuredContent"]["sent"] is True


async def test_a_send_after_the_permission_ended_is_refused_and_the_grants_own_limit_applies(client, db, gmail):
    await _deal(db)
    await _grant_send(client, db, per_day=1)
    token = await make_key(db)
    tok = (await preview(client, token))["structuredContent"]["preview_token"]
    assert (await confirm(client, token, tok))["structuredContent"]["sent"] is True
    async with db() as s:  # a second draft on the same deal, same day
        s.add(AgentProposal(proposal_id="p2", campaign_id="c1", deal_id="d_a", key="k2", kind="reply", status="pending", title="y",
                            payload={"message": TEXT + " Again.", "source": "agent"}))
        await s.commit()
    capped = await preview(client, token)
    assert capped["isError"] is True and "limit" in capped["content"][0]["text"] and "1 of 1" in capped["content"][0]["text"]
    async with db() as s:
        g = (await s.execute(select(AgentGrant))).scalar_one()
        g.valid_until = datetime.now(timezone.utc) - timedelta(minutes=1)
        await s.commit()
    ended = await preview(client, token)
    assert ended["isError"] is True and "permission to send ended" in ended["content"][0]["text"]


async def test_first_emails_need_their_own_permission_and_check_the_subject_and_history(client, db, gmail):
    await _deal(db, kind="pitch", payload={"subject": "A video about DataLaunch?"})
    token = await make_key(db)
    no = await preview(client, token)
    assert no["isError"] is True and "send_first_emails" in no["content"][0]["text"]
    await _grant_send(client, db, ability="send_first_emails")
    p = (await preview(client, token))["structuredContent"]
    assert p["kind"] == "pitch" and p["subject"] == "A video about DataLaunch?" and p["mode"] == "ask"
    sent = await confirm(client, token, p["preview_token"])
    assert sent["structuredContent"]["sent"] is True
    assert gmail.sent[0]["subject"] == "A video about DataLaunch?"
    [ev] = await sent_events(db)
    assert ev.payload["agent"] is True and ev.payload["kind"] == "pitch"


async def test_a_first_email_to_someone_the_founder_wrote_to_recently_is_left_to_them(client, db, gmail):
    await _deal(db, kind="pitch", payload={"subject": "Hi"})
    async with db() as s:
        camp = (await s.execute(select(Campaign).where(Campaign.campaign_id == "c1"))).scalar_one()
        camp.campaign_leads = [{**l, "contact": {"contacted_before": True}} if l["id"] == "UC_a" else l for l in camp.campaign_leads]
        await s.commit()
    await _grant_send(client, db, ability="send_first_emails")
    out = await preview(client, await make_key(db))
    assert out["isError"] is True and "wrote to this address recently" in out["content"][0]["text"]

"""send_message: the founder's agent sends a draft it wrote, only after a preview and the founder's yes (F9.7, step 3b).
Gmail is a fake sender; nothing here can email anyone."""

import time
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import select

from app.agent import constants as A
from app.models.campaign import Campaign
from app.models.deal import AgentProposal, CreatorDeal, DealEvent
from tests.mcp.conftest import call_tool, make_key

pytestmark = pytest.mark.asyncio

TEXT = "Hi Krish, thanks for getting back to me. Could we do $180 for the video? Your LangChain Crash Course is a great fit."


@pytest.fixture
def gmail(monkeypatch):
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    state = SimpleNamespace(sent=[], usable=True, fail=None, notes=[])
    account = SimpleNamespace(email="founder@example.com", user_id="u1")

    async def account_for(db, user_id):
        return account

    async def send_for_deal(db, acct, d, text, subject=None):
        if state.fail:
            raise state.fail
        state.sent.append({"to": d.contact_email, "text": text, "subject": subject})
        d.gmail_thread_id = "t1"
        return {"gmail_id": f"g{len(state.sent)}", "thread_id": "t1"}

    async def notice(db, acct, *, name, text, campaign_id, send_mail=None):
        state.notes.append({"name": name, "text": text, "campaign": campaign_id})

    monkeypatch.setattr("app.gmail.service.account_for", account_for)
    monkeypatch.setattr("app.gmail.service.usable", lambda a: state.usable)
    monkeypatch.setattr("app.gmail.service.send_for_deal", send_for_deal)
    monkeypatch.setattr("app.mcp.tools_send.notify_agent_send", notice)
    return state


async def seed(db, *, settings=None, source="agent", kind="send_counter", payload=None, email="krish@example.com"):
    async with db() as s:
        camp = (await s.execute(select(Campaign).where(Campaign.campaign_id == "c1"))).scalar_one()
        camp.outreach_settings = {"writer": "agent", "agent_send": True} if settings is None else settings
        s.add(CreatorDeal(deal_id="d_a", campaign_id="c1", creator_id="UC_a", creator_name="Krish Naik", stage="negotiating",
                          quoted_rate=250, fair_low=120, fair_high=200, contact_email=email, channel="email", gmail_thread_id="t0"))
        await s.flush()
        s.add(AgentProposal(proposal_id="p1", campaign_id="c1", deal_id="d_a", key="nego:e1", kind=kind, status="pending", title="Offer",
                            payload={"message": TEXT, "source": source, "terms": {"fee": 180, "commission_pct": 0}, **(payload or {})}))
        await s.commit()


async def preview(client, token):
    return await call_tool(client, token, "send_message", campaign_id="c1", deal_id="d_a")


async def confirm(client, token, tok):
    return await call_tool(client, token, "send_message", campaign_id="c1", deal_id="d_a", confirm=True, preview_token=tok)


async def proposal(db):
    async with db() as s:
        return (await s.execute(select(AgentProposal))).scalar_one()


async def sent_events(db):
    async with db() as s:
        return list((await s.execute(select(DealEvent).where(DealEvent.type == "message_sent"))).scalars())


# --- the preview ------------------------------------------------------------------------------------------

async def test_the_preview_shows_exactly_what_would_go_out_and_sends_nothing(client, db, gmail):
    await seed(db)
    token = await make_key(db)
    d = (await preview(client, token))["structuredContent"]
    assert d["sent"] is False and d["text"] == TEXT and d["to"] == "krish@example.com" and d["preview_token"]
    assert d["subject"] == "(reply in the same thread)" and d["sent_today_by_agent"] == 0
    assert gmail.sent == [] and await sent_events(db) == [] and (await proposal(db)).status == "pending"


# --- the switch and the allowed drafts --------------------------------------------------------------------

@pytest.mark.parametrize("settings", [{"writer": "agent"}, {"writer": "reachai", "agent_send": True}, {}])
async def test_off_by_default_and_only_when_the_agent_writes(client, db, gmail, settings):
    await seed(db, settings=settings)
    token = await make_key(db)
    out = await preview(client, token)
    assert out["isError"] is True and "Allow my agent to send" in out["content"][0]["text"] and gmail.sent == []


async def test_it_cannot_send_what_it_did_not_write_or_what_failed_its_checks(client, db, gmail):
    token = await make_key(db)
    await seed(db, source="ai")
    out = await preview(client, token)
    assert out["isError"] is True and "Only drafts your agent wrote" in out["content"][0]["text"]


async def test_held_drafts_wait_for_the_founder(client, db, gmail):
    await seed(db, payload={"held": "check_failed", "problems": ["grounded"]})
    out = await preview(client, await make_key(db))
    assert out["isError"] is True and "didn't pass" in out["content"][0]["text"]


@pytest.mark.parametrize("kind", ["agree", "mark_lost"])
async def test_agreeing_and_closing_always_need_the_founder_in_the_app(client, db, gmail, kind):
    await seed(db, kind=kind, source="agent")
    out = await preview(client, await make_key(db))
    assert out["isError"] is True and "need the founder in ReachAI" in out["content"][0]["text"] and gmail.sent == []


async def test_confirmations_are_never_sent_from_here_and_first_emails_need_their_own_permission(client, db, gmail):
    await seed(db, kind="confirm_terms")
    out = await preview(client, await make_key(db))
    assert out["isError"] is True and "no draft to send" in out["content"][0]["text"]
    async with db() as s:
        p = (await s.execute(select(AgentProposal))).scalar_one()
        p.kind = "pitch"
        await s.commit()
    out = await preview(client, await make_key(db))
    assert out["isError"] is True and "send_first_emails" in out["content"][0]["text"] and gmail.sent == []


async def test_it_needs_gmail_and_an_email_address(client, db, gmail):
    await seed(db)
    token = await make_key(db)
    gmail.usable = False
    assert "Gmail isn't connected" in (await preview(client, token))["content"][0]["text"]
    gmail.usable = True
    async with db() as s:
        d = (await s.execute(select(CreatorDeal))).scalar_one()
        d.contact_email, d.channel = None, None
        await s.commit()
    assert "no email route" in (await preview(client, token))["content"][0]["text"]


async def test_other_founders_campaigns_are_not_found(client, db, gmail):
    await seed(db)
    out = await call_tool(client, await make_key(db), "send_message", campaign_id="other", deal_id="d_a")
    assert out["isError"] is True and "not found" in out["content"][0]["text"].lower()


# --- the token ------------------------------------------------------------------------------------------

async def test_confirming_needs_the_token_from_a_preview(client, db, gmail):
    await seed(db)
    token = await make_key(db)
    for bad in (None, "", "nonsense", "abc.def"):
        out = await confirm(client, token, bad)
        assert out["isError"] is True and "preview" in out["content"][0]["text"].lower()
    assert gmail.sent == []


async def test_a_token_for_other_text_or_a_forged_one_is_refused(client, db, gmail):
    await seed(db)
    token = await make_key(db)
    tok = (await preview(client, token))["structuredContent"]["preview_token"]
    forged = tok.split(".")[0] + "." + "0" * 64
    assert "isn't valid" in (await confirm(client, token, forged))["content"][0]["text"]
    async with db() as s:  # the founder edits the draft after the preview
        p = (await s.execute(select(AgentProposal))).scalar_one()
        p.payload = {**p.payload, "message": TEXT + " Also, $5,000."}
        await s.commit()
    out = await confirm(client, token, tok)
    assert out["isError"] is True and "changed since the preview" in out["content"][0]["text"] and gmail.sent == []


async def test_an_old_preview_expires(client, db, gmail, monkeypatch):
    await seed(db)
    token = await make_key(db)
    tok = (await preview(client, token))["structuredContent"]["preview_token"]
    real = time.time
    monkeypatch.setattr("app.mcp.tools_send.time.time", lambda: real() + (A.SEND_PREVIEW_MINUTES + 1) * 60)
    out = await confirm(client, token, tok)
    assert out["isError"] is True and "older than" in out["content"][0]["text"] and gmail.sent == []


# --- sending -------------------------------------------------------------------------------------------

async def test_a_confirmed_send_goes_through_the_same_path_as_the_apps_approve_and_tells_the_founder(client, db, gmail):
    await seed(db)
    token = await make_key(db)
    tok = (await preview(client, token))["structuredContent"]["preview_token"]
    out = await confirm(client, token, tok)
    assert out["structuredContent"]["sent"] is True and out["structuredContent"]["sent_today_by_agent"] == 1
    assert gmail.sent == [{"to": "krish@example.com", "text": TEXT, "subject": None}]
    assert (await proposal(db)).status == "approved"
    [ev] = await sent_events(db)
    assert ev.payload["agent"] is True and ev.payload["text"] == TEXT and ev.payload["via"] == "gmail" and ev.payload["gmail_id"] == "g1"
    assert gmail.notes == [{"name": "Krish Naik", "text": TEXT, "campaign": "c1"}]  # the founder is emailed for every send
    again = await confirm(client, token, tok)
    assert again["isError"] is True and len(gmail.sent) == 1  # one send per draft


async def test_a_failed_send_gives_the_draft_back_and_records_nothing(client, db, gmail):
    gmail.fail = HTTPException(429, "You've sent 40 emails today.")
    await seed(db)
    token = await make_key(db)
    tok = (await preview(client, token))["structuredContent"]["preview_token"]
    out = await confirm(client, token, tok)
    assert out["isError"] is True and "Not sent" in out["content"][0]["text"] and "40 emails" in out["content"][0]["text"]
    assert (await proposal(db)).status == "pending" and await sent_events(db) == [] and gmail.notes == []
    gmail.fail = None
    assert (await confirm(client, token, tok))["structuredContent"]["sent"] is True  # nothing was lost: it can be sent now


async def test_agent_sends_are_capped_per_day(client, db, gmail):
    await seed(db)
    async with db() as s:
        for i in range(A.AGENT_SENDS_PER_DAY):
            s.add(DealEvent(deal_id="d_a", type="message_sent", payload={"text": f"m{i}", "agent": True}, created_at=datetime.now(timezone.utc)))
        s.add(DealEvent(deal_id="d_a", type="message_sent", payload={"text": "by the founder"}))  # doesn't count
        await s.commit()
    out = await preview(client, await make_key(db))
    assert out["isError"] is True and "limit" in out["content"][0]["text"] and gmail.sent == []


async def test_inbox_says_which_conversations_have_a_draft_the_agent_may_send(client, db, gmail):
    await seed(db)
    out = (await call_tool(client, await make_key(db), "inbox"))["structuredContent"]
    assert [i["can_send"] for i in out["items"] if i["deal_id"] == "d_a"] == [True]
    await seed_off(db)
    out = (await call_tool(client, await make_key(db), "inbox"))["structuredContent"]
    assert not any(i["can_send"] for i in out["items"])


async def seed_off(db):
    async with db() as s:
        camp = (await s.execute(select(Campaign).where(Campaign.campaign_id == "c1"))).scalar_one()
        camp.outreach_settings = {"writer": "agent", "agent_send": False}
        await s.commit()

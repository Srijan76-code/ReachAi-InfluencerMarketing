"""The founder's own agent writes replies and follow-ups; ReachAI checks them and saves drafts (F9.7, step 3a)."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.agent import constants as A
from app.models.campaign import Campaign
from app.models.deal import AgentProposal, CreatorDeal, DealEvent
from tests.mcp.conftest import call_tool, make_key
from tests.replies import fakes as F

pytestmark = pytest.mark.asyncio

ASK = "Thanks for reaching out! My rate for an integration is $250."
COUNTER = {"action": "counter", "price": {"fee": 180}, "their_ask": {"fee": 250},
           "message": "Hi Krish, thanks for getting back to me. Could we do $180 for the video? Your LangChain Crash Course is a great fit."}


@pytest.fixture
def jev_reply(monkeypatch):
    judge = F.jev()
    monkeypatch.setattr("app.judge.client.judge", judge)
    return judge


async def seed(db, *, writer="agent", task=True, follow_up=False):
    async with db() as s:
        camp = (await s.execute(select(Campaign).where(Campaign.campaign_id == "c1"))).scalar_one()
        camp.outreach_settings = {"writer": writer} if writer else None
        d = CreatorDeal(deal_id="d_a", campaign_id="c1", creator_id="UC_a", creator_name="Krish Naik", stage="negotiating",
                        quoted_rate=250, fair_low=120, fair_high=200, contact_email="krish@example.com", channel="email")
        s.add(d)
        await s.flush()
        s.add(DealEvent(deal_id="d_a", type="message_sent", payload={"text": "Hi Krish, would you make a video about DataLaunch?"}))
        ev = DealEvent(deal_id="d_a", type="creator_reply", payload={"text": ASK})
        s.add(ev)
        await s.flush()
        if task:
            s.add(AgentProposal(campaign_id="c1", deal_id="d_a", key=f"nego:{ev.event_id}", kind="agent_task", status="pending",
                                title="Your agent writes the reply", payload={"mode": "reply", "reply_event_id": ev.event_id,
                                                                              "signals": {"opt_out": 0, "injection": 0, "needs_founder": 0, "asks_question": 0.9}, "tries": 0}))
        if follow_up:
            s.add(AgentProposal(campaign_id="c1", deal_id="d_a", key="followup:1", kind="follow_up", status="pending",
                                title="Follow up", payload={"message": "Hi, just checking in.", "source": "template"}))
        await s.commit()
        return ev.event_id


async def proposals(db):
    async with db() as s:
        return list((await s.execute(select(AgentProposal))).scalars())


async def events(db, type_):
    async with db() as s:
        return list((await s.execute(select(DealEvent).where(DealEvent.type == type_))).scalars())


async def submit(client, token, draft, deal_id="d_a"):
    return await call_tool(client, token, "submit_reply", campaign_id="c1", deal_id=deal_id, draft=draft)


# --- reply_context -----------------------------------------------------------------------------------------

async def test_the_agent_gets_the_writers_context_with_the_creators_words_apart(client, db, jev_reply):
    await seed(db)
    token = await make_key(db)
    out = await call_tool(client, token, "reply_context", campaign_id="c1", deal_id="d_a")
    d = out["structuredContent"]
    assert d["mode"] == "reply" and d["tries_left"] == A.AGENT_REPLY_TRIES and "founder" in d["instructions"].lower()
    assert d["untrusted"]["creator_message"] == ASK and any("DataLaunch" in t["text"] for t in d["untrusted"]["conversation"])
    assert "creator_message" not in d["context"] and "conversation" not in d["context"] and d["hard_limits"]["fee_ceiling"]
    assert "action" in d["draft_format"] and jev_reply.calls == []  # reading costs nothing


async def test_it_only_works_where_the_founder_switched_it_on_and_on_their_own_campaigns(client, db, jev_reply):
    await seed(db, writer=None)
    token = await make_key(db)
    off = await call_tool(client, token, "reply_context", campaign_id="c1", deal_id="d_a")
    assert off["isError"] is True and "My agent writes replies" in off["content"][0]["text"]
    foreign = await call_tool(client, token, "reply_context", campaign_id="other", deal_id="d_a")
    assert foreign["isError"] is True and "not found" in foreign["content"][0]["text"].lower()


async def test_nothing_waiting_is_explained(client, db, jev_reply):
    await seed(db, task=False)
    token = await make_key(db)
    out = await call_tool(client, token, "reply_context", campaign_id="c1", deal_id="d_a")
    assert out["isError"] is True and "Nothing is waiting" in out["content"][0]["text"]


# --- submit_reply -------------------------------------------------------------------------------------------

async def test_a_checked_counter_becomes_the_draft_in_the_chat_and_nothing_is_sent(client, db, jev_reply):
    await seed(db)
    token = await make_key(db)
    out = await submit(client, token, COUNTER)
    assert out["structuredContent"]["status"] == "saved" and out["structuredContent"]["outcome"] == "send"
    rows = await proposals(db)
    assert len(rows) == 1  # the task became the draft: one suggestion per message
    p = rows[0]
    assert p.kind == "send_counter" and p.status == "pending" and p.payload["source"] == "agent"
    assert p.payload["terms"]["fee"] == 180 and "$180" in p.payload["message"]
    assert await events(db, "message_sent") and len(await events(db, "message_sent")) == 1  # only the founder's first email
    async with db() as s:
        d = (await s.execute(select(CreatorDeal))).scalar_one()
    assert d.quoted_rate == 250  # their ask recorded, exactly as for our own AI's replies


async def test_a_price_over_the_hard_limit_is_sent_back_before_any_jev_call(client, db, jev_reply):
    await seed(db)
    token = await make_key(db)
    out = await submit(client, token, {**COUNTER, "price": {"fee": 900}, "message": "Hi Krish, we can do $900 for the video."})
    d = out["structuredContent"]
    assert d["status"] == "rewrite" and d["passed"] is False and d["tries_left"] == A.AGENT_REPLY_TRIES - 1
    assert d["fix_these"][0]["check"] == "price_rule" and "hard limit" in d["fix_these"][0]["why"]
    assert jev_reply.calls == []
    task = (await proposals(db))[0]
    assert task.kind == "agent_task" and task.payload["tries"] == 1


async def test_after_three_failed_tries_the_founder_gets_the_last_draft_held(client, db, jev_reply):
    await seed(db)
    token = await make_key(db)
    bad = {**COUNTER, "price": {"fee": 900}, "message": "Hi Krish, we can do $900 for the video."}
    for _ in range(A.AGENT_REPLY_TRIES - 1):
        assert (await submit(client, token, bad))["structuredContent"]["status"] == "rewrite"
    last = await submit(client, token, bad)
    assert last["structuredContent"]["status"] == "hold"
    p = (await proposals(db))[0]
    assert p.kind == "send_counter" and p.payload["held"] == "check_failed" and p.payload["source"] == "agent" and p.payload["problems"]


async def test_an_unknown_action_is_refused(client, db, jev_reply):
    await seed(db)
    token = await make_key(db)
    bad_action = await submit(client, token, {**COUNTER, "action": "send_money"})
    assert bad_action["isError"] is True


async def test_jev_being_down_costs_no_try(client, db, monkeypatch):
    from app.judge.client import JudgeUnavailableError

    async def down(*a, **k):
        raise JudgeUnavailableError("down")

    monkeypatch.setattr("app.judge.client.judge", down)
    await seed(db)
    token = await make_key(db)
    out = await submit(client, token, COUNTER)
    assert out["isError"] is True and "no try was used" in out["content"][0]["text"]
    assert (await proposals(db))[0].payload["tries"] == 0


# --- follow-ups --------------------------------------------------------------------------------------------

async def test_the_agent_writes_the_follow_up_in_place_of_the_standard_one(client, db, jev_reply):
    await seed(db, task=False, follow_up=True)
    token = await make_key(db)
    ctx = await call_tool(client, token, "reply_context", campaign_id="c1", deal_id="d_a")
    assert ctx["structuredContent"]["mode"] == "follow_up"
    out = await submit(client, token, {"action": "reply", "message": "Hi Krish, I loved your LangChain Crash Course. Still keen on a DataLaunch video if the timing works."})
    assert out["structuredContent"]["status"] == "saved"
    p = (await proposals(db))[0]
    assert p.kind == "follow_up" and p.payload["source"] == "agent" and "LangChain" in p.payload["message"]
    priced = await submit(client, token, {**COUNTER})
    assert priced["isError"] is True  # nothing waiting now: the follow-up is already the agent's


async def test_a_follow_up_may_not_carry_a_price(client, db, jev_reply):
    await seed(db, task=False, follow_up=True)
    token = await make_key(db)
    out = await submit(client, token, {**COUNTER})
    assert out["isError"] is True and "plain message" in out["content"][0]["text"]


# --- inbox and the rest of the app -------------------------------------------------------------------------

async def test_inbox_lists_what_the_agent_writes(client, db, jev_reply):
    await seed(db, follow_up=False)
    token = await make_key(db)
    out = (await call_tool(client, token, "inbox"))["structuredContent"]
    mine = [i for i in out["items"] if i["deal_id"] == "d_a"]
    assert mine and mine[0]["writes_for_you"] == "reply" and out["writes_for_you"] == 1


async def test_autopilot_never_sends_what_the_agent_writes():
    from app.agent.autopilot import Settings, hold_reason
    from types import SimpleNamespace

    now = datetime.now(timezone.utc)
    p = SimpleNamespace(kind="send_counter", payload={"message": "Hi", "source": "agent"}, created_at=now)
    on = Settings(autopilot=True, review_first=False, since=None, writer="agent")
    assert hold_reason(p, SimpleNamespace(), None, on, email_route=True) == "manual"
    ours = Settings(autopilot=True, review_first=False, since=None, writer="reachai")
    assert hold_reason(p, SimpleNamespace(), None, ours, email_route=True) is None
    pitch = SimpleNamespace(kind="pitch", payload={"message": "Hi"}, created_at=now)
    assert hold_reason(pitch, SimpleNamespace(), {}, on, email_route=True) is None  # first emails still go (written by the pitch run)


# --- the app side: negotiate() only reads when the founder's agent writes ------------------------------------

async def test_negotiate_reads_but_does_not_write_when_the_agent_writes(db, monkeypatch):
    from app.negotiation.run import negotiate
    from app.replies.agent import ReplyResult

    ev_id = await seed(db, task=False)
    seen = {}

    async def fake_agent(ctx, *, context, read_only=False, **k):
        seen["read_only"] = read_only
        return ReplyResult("agent_task", None, "Your agent writes the reply on its schedule.", signals={"asks_question": 0.9})

    async with db() as s:
        d = (await s.execute(select(CreatorDeal))).scalar_one()
        reply = await s.get(DealEvent, ev_id)
        out = await negotiate(s, d, reply, lead={"id": "UC_a", "title": "Krish Naik"}, details={}, user_id="u1", agent=fake_agent)
        await s.commit()
    assert seen["read_only"] is True and out["action"] == "none"
    task = (await proposals(db))[0]
    assert task.kind == "agent_task" and task.payload["reply_event_id"] == ev_id and task.key == f"nego:{ev_id}"


async def test_negotiate_is_unchanged_when_our_own_ai_writes(db):
    from app.negotiation.run import negotiate
    from app.replies.agent import ReplyResult

    ev_id = await seed(db, writer="reachai", task=False)
    seen = {}

    async def fake_agent(ctx, *, context, **k):
        seen.update(k)
        return ReplyResult("hold", None, "ReachAI couldn't write this right now.")

    async with db() as s:
        d = (await s.execute(select(CreatorDeal))).scalar_one()
        reply = await s.get(DealEvent, ev_id)
        await negotiate(s, d, reply, lead={"id": "UC_a"}, details={}, user_id="u1", agent=fake_agent)
        await s.commit()
    assert "read_only" not in seen and await proposals(db) == []

"""F9.5: an agent asks the founder to send a reply, agree a price or record a payment. Nothing acts on its own."""

import pytest
from sqlalchemy import select

from app.models.deal import AgentProposal, CreatorDeal, DealEvent
from tests.mcp.conftest import call_tool, make_key

pytestmark = pytest.mark.asyncio

REPLY = "Thanks Krish, that works for us. Could you share two dates that suit you for the video next month?"
AGREE = "Great, Krish. Let's go with $210 for the video. I'll send the details and your link right after."


async def rows(db, model):
    async with db() as s:
        return (await s.execute(select(model))).scalars().all()


async def deal(db, *, stage="negotiating", sent=True, agreed_rate=None, **kw):
    async with db() as s:
        d = CreatorDeal(campaign_id="c1", creator_id="UC_a", creator_name="Krish Naik", stage=stage, fair_low=120,
                        fair_high=200, agreed_rate=agreed_rate, **kw)
        s.add(d)
        await s.flush()
        if sent:
            s.add(DealEvent(deal_id=d.deal_id, type="message_sent", payload={"text": "Hi Krish", "kind": "pitch"}))
        await s.commit()
        return d.deal_id


async def test_request_send_puts_a_reply_in_the_chat_and_sends_nothing(client, db):
    token = await make_key(db)
    await deal(db)
    result = await call_tool(client, token, "request_send", campaign_id="c1", creator_id="UC_a", message=REPLY)
    assert result["structuredContent"]["saved"] is True and "Nothing has been sent" in result["content"][0]["text"]
    (p,) = await rows(db, AgentProposal)
    assert p.kind == "reply" and p.key == "agent:reply" and p.status == "pending"
    assert p.payload["source"] == "agent" and p.payload["held"] == "from_agent"
    assert [e.type for e in await rows(db, DealEvent)] == ["message_sent"]  # only the earlier pitch
    again = await call_tool(client, token, "request_send", campaign_id="c1", creator_id="UC_a", message=REPLY + " Thanks!")
    assert again["structuredContent"]["replaced"] is True and len(await rows(db, AgentProposal)) == 1


async def test_request_send_refuses_prices_and_first_messages(client, db):
    token = await make_key(db)
    await deal(db, sent=False)
    first = await call_tool(client, token, "request_send", campaign_id="c1", creator_id="UC_a", message=REPLY)
    assert first["isError"] is True and "save_draft" in first["content"][0]["text"]
    async with db() as s:
        d = (await s.execute(select(CreatorDeal))).scalar_one()
        s.add(DealEvent(deal_id=d.deal_id, type="message_sent", payload={"text": "Hi"}))
        await s.commit()
    priced = await call_tool(client, token, "request_send", campaign_id="c1", creator_id="UC_a",
                             message="Thanks Krish, we can do $150 for the video if that works for you this month.")
    assert priced["isError"] is True and "request_agree" in priced["content"][0]["text"]
    assert await rows(db, AgentProposal) == []


async def test_request_send_waits_for_reachais_own_draft(client, db):
    token = await make_key(db)
    deal_id = await deal(db)
    async with db() as s:
        s.add(AgentProposal(campaign_id="c1", deal_id=deal_id, key="nego:1", kind="send_counter", status="pending",
                            title="Counter", reason="r", payload={"message": "Hi Krish, how about $150?"}))
        await s.commit()
    result = await call_tool(client, token, "request_send", campaign_id="c1", creator_id="UC_a", message=REPLY)
    assert result["isError"] is True and "already waiting" in result["content"][0]["text"]


async def test_request_agree_is_held_to_the_hard_limit(client, db):
    token = await make_key(db)
    await deal(db)
    over = await call_tool(client, token, "request_agree", campaign_id="c1", creator_id="UC_a", fee_usd=400,
                           message="Great, Krish. Let's go with $400 for the video. Details to follow shortly.")
    assert over["isError"] is True and "hard limit of $229" in over["content"][0]["text"]  # 200 x 1.15, rounded down
    wrong = await call_tool(client, token, "request_agree", campaign_id="c1", creator_id="UC_a", fee_usd=210,
                            message="Great, Krish. Let's go with $220 for the video. Details to follow shortly.")
    assert wrong["isError"] is True and "only price it may state is $210" in wrong["content"][0]["text"]
    ok = await call_tool(client, token, "request_agree", campaign_id="c1", creator_id="UC_a", fee_usd=210, message=AGREE)
    assert ok["structuredContent"]["hard_limit_usd"] == 229 and "Nothing is agreed or sent" in ok["content"][0]["text"]
    (p,) = await rows(db, AgentProposal)
    assert p.kind == "agree" and p.payload["agreed_rate"] == 210 and p.payload["deal_type"] == "flat"
    (d,) = await rows(db, CreatorDeal)
    assert d.stage == "negotiating" and d.agreed_rate is None  # nothing agreed until the founder confirms


async def test_request_agree_never_goes_below_an_earlier_offer_or_after_agreeing(client, db):
    token = await make_key(db)
    deal_id = await deal(db)
    async with db() as s:
        s.add(DealEvent(deal_id=deal_id, type="message_sent", payload={"text": "How about $180?", "terms": {"fee": 180}}))
        await s.commit()
    low = await call_tool(client, token, "request_agree", campaign_id="c1", creator_id="UC_a", fee_usd=150,
                          message="Great, Krish. Let's go with $150 for the video. Details to follow shortly.")
    assert low["isError"] is True and "below the $180" in low["content"][0]["text"]
    async with db() as s:
        d = (await s.execute(select(CreatorDeal))).scalar_one()
        d.stage, d.agreed_rate = "agreed", 180
        await s.commit()
    done = await call_tool(client, token, "request_agree", campaign_id="c1", creator_id="UC_a", fee_usd=190, message=AGREE)
    assert done["isError"] is True and "agreed" in done["content"][0]["text"]


async def test_request_mark_paid_leaves_it_for_the_founder_in_track(client, db):
    token = await make_key(db)
    await deal(db, stage="live", agreed_rate=180)
    result = await call_tool(client, token, "request_mark_paid", campaign_id="c1", creator_id="UC_a", method="upi",
                             note="UTR 1234")
    assert result["structuredContent"]["amount_usd"] == 180 and "Nothing is recorded" in result["content"][0]["text"]
    (p,) = await rows(db, AgentProposal)
    assert p.kind == "mark_paid" and p.key == "agent:paid" and p.payload["method"] == "upi"
    (d,) = await rows(db, CreatorDeal)
    assert d.stage == "live" and d.paid_at is None
    bad = await call_tool(client, token, "request_mark_paid", campaign_id="c1", creator_id="UC_a", method="cash")
    assert bad["isError"] is True


async def test_request_mark_paid_needs_an_agreed_price(client, db):
    token = await make_key(db)
    await deal(db)
    result = await call_tool(client, token, "request_mark_paid", campaign_id="c1", creator_id="UC_a")
    assert result["isError"] is True and "no agreed price" in result["content"][0]["text"]


async def test_requests_cannot_touch_another_users_campaign(client, db):
    token = await make_key(db)
    result = await call_tool(client, token, "request_send", campaign_id="other", creator_id="UC_a", message=REPLY)
    assert result["isError"] is True and await rows(db, AgentProposal) == []

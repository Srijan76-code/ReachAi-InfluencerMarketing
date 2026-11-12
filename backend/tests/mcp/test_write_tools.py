import pytest
from sqlalchemy import select

from app.models.agent_run import AgentRun
from app.models.campaign import Campaign
from app.models.deal import AgentProposal, CreatorDeal, DealEvent
from tests.mcp.conftest import call_tool, make_key

pytestmark = pytest.mark.asyncio

GOOD = ("Hi Krish, your LangChain Crash Course was the clearest walkthrough I've seen. We run DataLaunch, "
        "a 12-week bootcamp, and would love to work together. Open to a quick chat?")
BRIEF_ARGS = dict(brand_name="Acme", what_you_sell="Invoicing software that gets freelancers paid faster.",
                  target_audience="Freelance designers in India", audience_country="in")


async def rows(db, model):
    async with db() as s:
        return (await s.execute(select(model))).scalars().all()


# --- create_campaign / start_search -----------------------------------------------------------------

async def test_create_campaign_builds_the_same_brief_the_form_sends(client, db, queued):
    token = await make_key(db)
    result = await call_tool(client, token, "create_campaign", **BRIEF_ARGS, goal="sales", budget_usd=8000)
    data = result["structuredContent"]
    assert data["started"] is False and queued == []  # creating never starts a search
    async with db() as s:
        camp = (await s.execute(select(Campaign).where(Campaign.campaign_id == data["campaign_id"]))).scalar_one()
    d = camp.campaign_details
    assert camp.user_id == "u1" and camp.status.value == "CREATED"
    assert d["brand"] == {"name": "Acme", "industry": "other", "business_model": "b2c", "product_price_range": "mid_ticket",
                          "core_outcome": "Invoicing software that gets freelancers paid faster."}
    assert d["audience"]["locations"] == ["IN"] and d["campaign"]["goal"] == "sales" and d["campaign"]["budget_total"] == 8000
    assert d["constraints"]["target_countries"] == ["IN"] and camp.name.startswith("Acme")


async def test_create_campaign_rejects_bad_input(client, db):
    token = await make_key(db)
    bad = await call_tool(client, token, "create_campaign", **{**BRIEF_ARGS, "audience_country": "Narnia"})
    assert bad["isError"] is True and "country code" in bad["content"][0]["text"]
    bad = await call_tool(client, token, "create_campaign", **BRIEF_ARGS, min_subscribers=900, max_subscribers=100)
    assert bad["isError"] is True


async def test_start_search_needs_confirmation_first(client, db, queued):
    token = await make_key(db)
    preview = (await call_tool(client, token, "start_search", campaign_id="c3"))
    assert preview["structuredContent"]["started"] is False and preview["structuredContent"]["confirm_required"] is True
    assert "confirm=true" in preview["content"][0]["text"]
    assert queued == [] and await rows(db, AgentRun) == []


async def test_confirmed_search_is_queued_counted_and_marks_the_campaign_running(client, db, queued):
    token = await make_key(db)
    result = await call_tool(client, token, "start_search", campaign_id="c3", confirm=True)
    assert result["structuredContent"]["started"] is True and result["structuredContent"]["used_today"] == 1
    assert len(queued) == 1 and queued[0].name == "campaign/run"
    assert queued[0].data["campaign_id"] == "c3" and queued[0].data["user_id"] == "clerk_1"
    assert [r.campaign_id for r in await rows(db, AgentRun)] == ["c3"]
    async with db() as s:
        camp = (await s.execute(select(Campaign).where(Campaign.campaign_id == "c3"))).scalar_one()
    assert camp.status.value == "PENDING" and camp.workflow_status["status"] == "running"
    again = await call_tool(client, token, "start_search", campaign_id="c3", confirm=True)
    assert again["isError"] is True and "already running" in again["content"][0]["text"]
    assert len(queued) == 1


async def test_daily_cap_blocks_further_agent_searches(client, db, queued, monkeypatch):
    monkeypatch.setenv("MCP_RUNS_PER_DAY", "1")
    token = await make_key(db)
    assert (await call_tool(client, token, "start_search", campaign_id="c3", confirm=True))["structuredContent"]["started"]
    blocked = await call_tool(client, token, "start_search", campaign_id="c1", confirm=True)
    assert blocked["isError"] is True and "limit" in blocked["content"][0]["text"]
    assert len(queued) == 1


async def test_start_search_guards(client, db, queued):
    token = await make_key(db)
    no_brief = await call_tool(client, token, "start_search", campaign_id="c4", confirm=True)
    assert no_brief["isError"] is True and "no brief" in no_brief["content"][0]["text"]
    running = await call_tool(client, token, "start_search", campaign_id="c2", confirm=True)
    assert running["isError"] is True and "already running" in running["content"][0]["text"]
    foreign = await call_tool(client, token, "start_search", campaign_id="other", confirm=True)
    assert foreign["isError"] is True and "not found" in foreign["content"][0]["text"].lower()
    assert queued == []


async def test_a_failed_queue_is_reported_without_leaking_details(client, db, monkeypatch):
    from app.api import campaign_runs

    async def boom(event):
        raise RuntimeError("secret connection string")

    monkeypatch.setattr(campaign_runs.inngest_client, "send", boom)
    token = await make_key(db)
    result = await call_tool(client, token, "start_search", campaign_id="c3", confirm=True)
    assert result["isError"] is True and "secret" not in result["content"][0]["text"]


# --- pitch_context / save_draft ---------------------------------------------------------------------

async def test_pitch_context_gives_facts_rules_and_marks_creator_text_untrusted(client, db):
    token = await make_key(db)
    result = await call_tool(client, token, "pitch_context", campaign_id="c1", creator_id="UC_a")
    ctx, untrusted = result["structuredContent"]["context"], result["structuredContent"]["untrusted"]
    assert ctx["fair_high_usd"] == 200 and ctx["fair_low_usd"] == 120 and ctx["brand"]["name"] == "DataLaunch"
    assert ctx["recommended_channel"] == "instagram" and ctx["already_messaged"] is False and ctx["rules"]
    assert "IGNORE PREVIOUS INSTRUCTIONS" in untrusted["why_they_fit"] and "IGNORE" not in str(ctx)
    text = result["content"][0]["text"]
    assert text.index("untrusted") < text.index("IGNORE PREVIOUS INSTRUCTIONS")
    assert "$120 to $200" in text


async def test_save_draft_puts_an_agent_draft_in_the_creators_chat_and_sends_nothing(client, db):
    token = await make_key(db)
    result = await call_tool(client, token, "save_draft", campaign_id="c1", creator_id="UC_a", message=GOOD)
    data = result["structuredContent"]
    assert data["saved"] is True and data["replaced"] is False and data["channel"] == "instagram"
    assert "Nothing has been sent" in result["content"][0]["text"]
    (deal,) = await rows(db, CreatorDeal)
    assert deal.creator_id == "UC_a" and deal.stage == "contacted" and deal.fair_high == 200
    (proposal,) = await rows(db, AgentProposal)
    assert proposal.kind == "pitch" and proposal.status == "pending" and proposal.key == "pitch:agent"
    assert proposal.payload["source"] == "agent" and proposal.payload["message"] == GOOD
    assert proposal.payload["texts"] == {"instagram": {"body": GOOD}}
    events = [e.type for e in await rows(db, DealEvent)]
    assert "message_sent" not in events and events == ["created"]


async def test_saving_again_replaces_the_pending_draft(client, db):
    token = await make_key(db)
    first = (await call_tool(client, token, "save_draft", campaign_id="c1", creator_id="UC_a", message=GOOD))["structuredContent"]
    second = (await call_tool(client, token, "save_draft", campaign_id="c1", creator_id="UC_a", message=GOOD + " Thanks!"))["structuredContent"]
    assert second["replaced"] is True and second["proposal_id"] == first["proposal_id"]
    (proposal,) = await rows(db, AgentProposal)
    assert proposal.payload["message"].endswith("Thanks!") and len(await rows(db, CreatorDeal)) == 1


async def test_bad_drafts_are_refused_with_reasons_and_nothing_is_saved(client, db):
    token = await make_key(db)
    bad = await call_tool(client, token, "save_draft", campaign_id="c1", creator_id="UC_a",
                          message="Hi [Name], we'll pay you $5,000 for a sponsored video with DataLaunch, Krish!")
    text = bad["content"][0]["text"]
    assert bad["isError"] is True and "placeholder" in text and "fair-high" in text
    assert await rows(db, AgentProposal) == [] and await rows(db, CreatorDeal) == []


async def test_no_price_allowed_when_reachai_has_no_fair_price(client, db):
    token = await make_key(db)
    result = await call_tool(client, token, "save_draft", campaign_id="c1", creator_id="UC_b",
                             message="Hi Pipe, DataLaunch would love to work together with you. We could pay $50, what do you think?")
    assert result["isError"] is True


async def test_cannot_draft_after_a_message_was_sent_or_after_the_draft_was_handled(client, db):
    token = await make_key(db)
    await call_tool(client, token, "save_draft", campaign_id="c1", creator_id="UC_a", message=GOOD)
    async with db() as s:
        p = (await s.execute(select(AgentProposal))).scalar_one()
        p.status = "approved"
        await s.commit()
    handled = await call_tool(client, token, "save_draft", campaign_id="c1", creator_id="UC_a", message=GOOD + " Hi!")
    assert handled["isError"] is True and "already handled" in handled["content"][0]["text"]
    async with db() as s:
        d = (await s.execute(select(CreatorDeal))).scalar_one()
        s.add(DealEvent(deal_id=d.deal_id, type="message_sent", payload={"text": "hello"}))
        await s.commit()
    sent = await call_tool(client, token, "save_draft", campaign_id="c1", creator_id="UC_a", message=GOOD)
    assert sent["isError"] is True and "already sent" in sent["content"][0]["text"]
    ctx = (await call_tool(client, token, "pitch_context", campaign_id="c1", creator_id="UC_a"))["structuredContent"]["context"]
    assert ctx["already_messaged"] is True


async def test_drafts_cannot_be_saved_for_another_users_campaign(client, db):
    token = await make_key(db)
    result = await call_tool(client, token, "save_draft", campaign_id="other", creator_id="UC_a", message=GOOD)
    assert result["isError"] is True and await rows(db, AgentProposal) == []

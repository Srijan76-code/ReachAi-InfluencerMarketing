"""The founder's own agent words the "Why this creator" bullets and ReachAI checks them (F9.6)."""

import pytest
from sqlalchemy import select

from app.judge import constants as K
from app.models.campaign import Campaign
from tests.mcp.conftest import LEADS, call_tool, make_key

pytestmark = pytest.mark.asyncio

POINTS = {"why": "Their videos cover ML careers", "proof": "How I got my first ML job",
          "watch": {"kind": "weakness", "fact": "where their audience lives isn't clear"}, "choose": "A small test deal first"}
GOOD = ["They make videos about ML careers, as 'How I got my first ML job' shows.",
        "Watch out: where their audience lives isn't clear.",
        "A small test deal first."]


async def seed(db, *, source="facts", attempts=0, with_facts=True):
    leads = [dict(l) for l in LEADS]
    if with_facts:
        leads[0].update(reason_facts={"points": POINTS, "verdict": "Strong Buy"}, reason_source=source, reason_attempts=attempts)
    async with db() as s:
        camp = (await s.execute(select(Campaign).where(Campaign.campaign_id == "c1"))).scalar_one()
        camp.campaign_leads = leads
        await s.commit()


async def lead_a(db):
    async with db() as s:
        camp = (await s.execute(select(Campaign).where(Campaign.campaign_id == "c1"))).scalar_one()
    return next(l for l in camp.campaign_leads if l["id"] == "UC_a")


async def submit(client, token, bullets, creator_id="UC_a"):
    return await call_tool(client, token, "submit_reasons", campaign_id="c1", items=[{"creator_id": creator_id, "bullets": bullets}])


async def test_get_creator_hands_over_the_facts_and_the_benchmarked_prompt(client, db, jev):
    await seed(db)
    token = await make_key(db)
    out = (await call_tool(client, token, "get_creator", campaign_id="c1", creator_id="UC_a"))
    w = out["structuredContent"]["write_why"]
    assert w["facts"] == POINTS and w["tries_left"] == K.AGENT_REASON_ATTEMPTS and w["verdict"] == "Strong Buy"
    assert "WHY: Their videos cover ML careers" in w["prompt"] and "submit_reasons" in out["content"][0]["text"]
    assert jev.calls == []  # reading costs nothing


async def test_no_write_why_when_our_own_ai_wrote_it_or_it_is_done(client, db, jev):
    token = await make_key(db)
    await seed(db, with_facts=False)
    assert "write_why" not in (await call_tool(client, token, "get_creator", campaign_id="c1", creator_id="UC_a"))["structuredContent"]
    await seed(db, source="agent")
    assert "write_why" not in (await call_tool(client, token, "get_creator", campaign_id="c1", creator_id="UC_a"))["structuredContent"]


async def test_good_bullets_pass_jev_and_replace_the_plain_facts(client, db, jev):
    await seed(db)
    token = await make_key(db)
    out = await submit(client, token, GOOD)
    r = out["structuredContent"]["results"][0]
    assert r["status"] == "passed" and r["passed"] is True
    lead = await lead_a(db)
    assert lead["reason_source"] == "agent" and lead["reason_points"] == GOOD and lead["llm_reasoning"] == " ".join(GOOD)
    assert lead["reason_attempts"] == 1 and len(jev.calls) == 1


async def test_bullets_that_invent_something_come_back_with_what_to_fix(client, db, jev):
    jev.scores = {"grounded_0": 0.1}
    await seed(db)
    token = await make_key(db)
    r = (await submit(client, token, GOOD))["structuredContent"]["results"][0]
    assert r["status"] == "rewrite" and r["tries_left"] == K.AGENT_REASON_ATTEMPTS - 1
    assert r["fix_these"][0]["bullet"] == 1 and "not in the facts" in r["fix_these"][0]["check"]
    assert "bullet 2" in r["what_was_right"] and (await lead_a(db))["reason_source"] == "facts"  # nothing unchecked is saved


async def test_a_code_rule_breaks_before_any_jev_call(client, db, jev):
    await seed(db)
    token = await make_key(db)
    r = (await submit(client, token, ["Her videos are great.", "Watch out: unclear.", "Try a test deal."]))["structuredContent"]["results"][0]
    assert r["status"] == "rewrite" and "gender" in r["fix_these"][0]["check"] and jev.calls == []


async def test_after_the_allowed_tries_the_plain_facts_stay(client, db, jev):
    jev.scores = {"agrees": 0.1}
    await seed(db, attempts=K.AGENT_REASON_ATTEMPTS - 1)
    token = await make_key(db)
    r = (await submit(client, token, GOOD))["structuredContent"]["results"][0]
    assert r["status"] == "facts_kept" and r["tries_left"] == 0
    again = (await submit(client, token, GOOD))["structuredContent"]["results"][0]
    assert again["status"] == "facts_kept" and len(jev.calls) == 1  # no more paid checks once the tries are used
    assert (await lead_a(db))["reason_source"] == "facts"


async def test_jev_being_down_saves_nothing_and_costs_no_try(client, db, jev):
    jev.down = True
    await seed(db)
    token = await make_key(db)
    r = (await submit(client, token, GOOD))["structuredContent"]["results"][0]
    lead = await lead_a(db)
    assert r["status"] == "check_unavailable" and lead["reason_attempts"] == 0 and lead["reason_source"] == "facts"


async def test_other_cases_are_explained_not_errors(client, db, jev):
    await seed(db, with_facts=False)
    token = await make_key(db)
    assert (await submit(client, token, GOOD))["structuredContent"]["results"][0]["status"] == "not_applicable"
    assert (await submit(client, token, GOOD, creator_id="nope"))["structuredContent"]["results"][0]["status"] == "not_found"
    await seed(db, source="agent")
    assert (await submit(client, token, GOOD))["structuredContent"]["results"][0]["status"] == "already_written"
    assert jev.calls == []


async def test_it_only_touches_the_founders_own_campaigns_and_asks_for_three_bullets(client, db, jev):
    await seed(db)
    token = await make_key(db)
    foreign = await call_tool(client, token, "submit_reasons", campaign_id="other", items=[{"creator_id": "UC_a", "bullets": GOOD}])
    assert foreign["isError"] is True and "not found" in foreign["content"][0]["text"].lower()
    short = await submit(client, token, GOOD[:2])
    assert short["isError"] is True
    twice = await call_tool(client, token, "submit_reasons", campaign_id="c1",
                            items=[{"creator_id": "UC_a", "bullets": GOOD}, {"creator_id": "UC_a", "bullets": GOOD}])
    assert twice["isError"] is True and "once" in twice["content"][0]["text"]

"""Running a campaign from an agent (F9.8, 8c): add creators to deals, autopilot, Track goal and snippet. Each tool needs the
founder's permission for that campaign, and does what the website's own button does."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.agent import grants
from app.agent.autopilot import settings_of
from app.models.agent_grant import AgentGrant
from app.models.campaign import Campaign
from app.models.deal import CreatorDeal, DealEvent
from tests.mcp.conftest import call_tool, make_key

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def no_autopilot_start(monkeypatch):
    started = []

    async def start(user_ids):
        started.append(list(user_ids))

    monkeypatch.setattr("app.inngest.functions.start_autopilot", start)
    return started


async def allow(client, db, ability, campaign="c1"):
    d = (await call_tool(client, await make_key(db), "request_permission", campaign_id=campaign, ability=ability))["structuredContent"]
    async with db() as s:
        await grants.decide(s, "u1", d["user_code"], True)


async def deals(db):
    async with db() as s:
        return list((await s.execute(select(CreatorDeal))).scalars())


@pytest.mark.parametrize("tool,args,ability", [
    ("add_to_deals", {"creator_ids": ["UC_a"]}, "manage_campaign"),
    ("set_autopilot", {"on": True}, "autopilot"),
    ("track_setup", {"goal_kind": "signups", "goal_count": 100}, "manage_campaign"),
    ("track_snippet", {}, "manage_campaign"),
])
async def test_each_tool_needs_the_founders_permission_and_says_how_to_ask(client, db, tool, args, ability):
    out = await call_tool(client, await make_key(db), tool, campaign_id="c1", **args)
    text = out["content"][0]["text"]
    assert out["isError"] is True and f"'{ability}'" in text and "request_permission" in text
    assert await deals(db) == []


async def test_a_permission_for_one_campaign_does_not_cover_another_or_outlive_its_end(client, db):
    await allow(client, db, "manage_campaign", "c1")
    token = await make_key(db)
    other = await call_tool(client, token, "track_snippet", campaign_id="c3")
    assert other["isError"] is True and "request_permission" in other["content"][0]["text"]
    async with db() as s:
        g = (await s.execute(select(AgentGrant))).scalar_one()
        g.valid_until = datetime.now(timezone.utc) - timedelta(minutes=1)
        await s.commit()
    ended = await call_tool(client, token, "track_snippet", campaign_id="c1")
    assert ended["isError"] is True and "request_permission" in ended["content"][0]["text"]
    foreign = await call_tool(client, token, "add_to_deals", campaign_id="other", creator_ids=["UC_a"])
    assert foreign["isError"] is True and "not found" in foreign["content"][0]["text"].lower()


async def test_add_to_deals_creates_a_chat_for_each_creator_and_skips_repeats_and_strangers(client, db):
    await allow(client, db, "manage_campaign")
    token = await make_key(db)
    out = await call_tool(client, token, "add_to_deals", campaign_id="c1", creator_ids=["UC_a", "UC_c", "UC_nobody"])
    d = out["structuredContent"]
    assert len(d["created"]) == 2 and d["skipped"] == 0 and d["not_in_campaign"] == ["UC_nobody"]
    assert "Added 2 creators" in out["content"][0]["text"] and "not in this campaign's results: UC_nobody" in out["content"][0]["text"]
    assert {x.creator_id for x in await deals(db)} == {"UC_a", "UC_c"}
    async with db() as s:
        assert len((await s.execute(select(DealEvent).where(DealEvent.type == "created"))).scalars().all()) == 2
    again = (await call_tool(client, token, "add_to_deals", campaign_id="c1", creator_ids=["UC_a"]))["structuredContent"]
    assert again["created"] == [] and again["skipped"] == 1 and len(await deals(db)) == 2


async def test_set_autopilot_changes_the_campaign_setting_like_the_website_does(client, db, no_autopilot_start):
    await allow(client, db, "autopilot")
    token = await make_key(db)
    on = await call_tool(client, token, "set_autopilot", campaign_id="c1", on=True, review_first=True)
    assert on["structuredContent"] == {"autopilot": True, "review_first": True} and "first emails wait" in on["content"][0]["text"]
    async with db() as s:
        camp = (await s.execute(select(Campaign).where(Campaign.campaign_id == "c1"))).scalar_one()
    assert settings_of(camp.outreach_settings).autopilot is True and no_autopilot_start == [["u1"]]
    off = await call_tool(client, token, "set_autopilot", campaign_id="c1", on=False)
    assert off["structuredContent"]["autopilot"] is False


async def test_track_goal_is_saved_and_checked(client, db):
    await allow(client, db, "manage_campaign")
    token = await make_key(db)
    ok = await call_tool(client, token, "track_setup", campaign_id="c1", goal_kind="sales", goal_count=50, value_each=29.0)
    assert ok["isError"] is False
    async with db() as s:
        camp = (await s.execute(select(Campaign).where(Campaign.campaign_id == "c1"))).scalar_one()
    assert camp.campaign_details["track"] == {"goal_kind": "sales", "goal_count": 50, "value_each": 29.0}
    bad = await call_tool(client, token, "track_setup", campaign_id="c1", goal_kind="signups", goal_count=0)
    assert bad["isError"] is True  # a goal needs to be above zero


async def test_the_snippet_is_the_same_each_time_and_says_how_to_confirm(client, db):
    await allow(client, db, "manage_campaign")
    token = await make_key(db)
    one = await call_tool(client, token, "track_snippet", campaign_id="c1")
    two = await call_tool(client, token, "track_snippet", campaign_id="c1")
    d = one["structuredContent"]
    assert d["key"] == two["structuredContent"]["key"] and d["snippet"].startswith('<script src="') and f'data-key="{d["key"]}"' in d["snippet"]
    assert d["endpoint"].endswith(f"/api/t/{d['key']}") and "?reachai_test=1" in one["content"][0]["text"] and d["seen_at"] is None

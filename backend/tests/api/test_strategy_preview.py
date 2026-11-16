"""The strategy preview on the brief page (F1.24b): what ReachAI will search for, before credits are spent, editable."""

import pytest
from sqlalchemy import select

from app.discovery import strategy_preview as SP
from app.discovery.brief import parse_brief
from app.discovery.prompts import StrategyOut
from app.llm.client import LLMUnavailableError
from app.models.cost_event import CostEvent
from app.models.discovery_run import RunStrategy
from tests.api.test_device_login import approved_key, env  # noqa: F401  (the app, database and sign-in fixture)

pytestmark = pytest.mark.asyncio

DETAILS = {
    "brand": {"name": "DataLaunch", "industry": "edtech", "business_model": "b2c", "product_price_range": "high_ticket",
              "core_outcome": "A 12-week data science bootcamp that guarantees a job or refunds tuition."},
    "audience": {"target_persona": "Fresh CS graduates moving into AI/ML roles", "locations": ["IN"], "languages": ["en"]},
    "campaign": {"goal": "signups", "creator_authority_level": "mentor", "budget_total": 5000, "creator_count": 5},
    "constraints": {"min_subscribers": 10000, "max_subscribers": 500000, "target_countries": ["IN"], "exclude_kids_content": True},
}
STRATEGY = StrategyOut(
    topics=["data science career", "machine learning roadmap", "python for beginners"], pain_points=["getting a first ML job"], formats=["tutorial"],
    youtube_queries=["machine learning roadmap", "data science for freshers", "python for ai", "learn machine learning", "ai jobs india", "data analyst skills"],
    trend_topics=["AI agents"], competitors=["upGrad"], safety_level="medium", primary_metric="creator_authority")


@pytest.fixture
def ai(monkeypatch):
    calls = []

    async def fake(route, prompt, schema=None, **kw):
        calls.append((route, prompt))
        return STRATEGY

    monkeypatch.setattr("app.discovery.strategy_preview.achat", fake)
    return calls


async def preview(env, details=DETAILS):
    env.as_founder(True)
    return await env.c.post("/api/campaigns/strategy-preview", json={"details": details})


async def test_the_preview_makes_the_strategy_once_stores_it_under_the_searchs_key_and_serves_repeats_free(env, ai):
    first = (await preview(env)).json()
    again = (await preview(env)).json()
    assert first["cached"] is False and again["cached"] is True and again["strategy"] == first["strategy"]
    assert len(ai) == 1 and ai[0][0] == "strategy" and "DataLaunch" in ai[0][1]
    async with env.sf() as db:
        row = (await db.execute(select(RunStrategy))).scalar_one()
    assert row.brief_hash == SP.brief_key(parse_brief(DETAILS))  # the very key the search looks up, so it reuses this


async def test_changing_the_brief_makes_a_new_strategy_but_competitors_and_agent_leftovers_do_not(env, ai):
    await preview(env)
    other = {**DETAILS, "audience": {**DETAILS["audience"], "target_persona": "Working analysts who want to move into ML"}}
    assert (await preview(env, other)).json()["cached"] is False
    same = {**DETAILS, "campaign": {**DETAILS["campaign"], "competitors": ["upGrad"], "competitor_mode": "avoid",
                                    "ai_mode": "agent", "chosen_strategy": {"topics": ["x"]}}}
    assert (await preview(env, same)).json()["cached"] is True  # an old edit or agent mode never changes what is previewed
    assert len(ai) == 2


async def test_it_asks_for_the_basics_first(env, ai):
    r = await preview(env, {"brand": {"name": "DataLaunch"}})
    assert r.status_code == 422 and "Fill in your brand" in r.json()["detail"] and ai == []


async def test_it_says_so_when_the_ai_is_down_and_the_search_is_still_possible(env, monkeypatch):
    async def down(*a, **k):
        raise LLMUnavailableError("all failed")

    monkeypatch.setattr("app.discovery.strategy_preview.achat", down)
    r = await preview(env)
    assert r.status_code == 503 and "still start the search" in r.json()["detail"]


async def test_there_is_a_daily_limit_on_fresh_previews_and_repeats_do_not_count(env, ai):
    async with env.sf() as db:
        db.add_all([CostEvent(user_id="u1", provider="x", sku="m", route="strategy", run_id=None) for _ in range(SP.PREVIEWS_PER_DAY)])
        db.add(CostEvent(user_id="u1", provider="x", sku="m", route="strategy", run_id="a-real-search"))  # a search's own strategy: not a preview
        await db.commit()
    capped = await preview(env, {**DETAILS, "brand": {**DETAILS["brand"], "name": "Another"}})
    assert capped.status_code == 429 and "previewed 30" in capped.json()["detail"]


async def test_an_agents_key_cannot_preview(env, ai):
    _, key = await approved_key(env)
    r = await env.c.post("/api/campaigns/strategy-preview", json={"details": DETAILS}, headers={"Authorization": f"Bearer {key}"})
    assert r.status_code == 403 and ai == []


# --- the founder's edit ----------------------------------------------------------------------------------

def edited(**change):
    return parse_brief({**DETAILS, "campaign": {**DETAILS["campaign"], "chosen_strategy": {**STRATEGY.model_dump(), **change}}})


def test_no_edit_means_nothing_to_check():
    assert SP.check_chosen(parse_brief(DETAILS)) is None


def test_a_sensible_edit_is_accepted_and_cleaned():
    out = SP.check_chosen(edited(topics=["  data   science  career ", "ml roadmap", "python"]))
    assert out["topics"] == ["data science career", "ml roadmap", "python"]


@pytest.mark.parametrize("change,words", [
    ({"youtube_queries": ["too few", "searches here"]}, "needs 6-12"),
    ({"youtube_queries": ["datalaunch bootcamp", "a b c d e f g", "x", "y z", "p q", "r s"]}, "Your search needs changes"),
    ({"topics": ["only one"]}, "topics needs"),
])
def test_a_bad_edit_says_what_to_change(change, words):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as e:
        SP.check_chosen(edited(**change))
    assert e.value.status_code == 422 and words in e.value.detail


async def test_starting_a_search_with_a_bad_edit_is_refused_before_any_credits_are_held(env):
    env.as_founder(True)
    bad = {**DETAILS, "campaign": {**DETAILS["campaign"], "chosen_strategy": {**STRATEGY.model_dump(), "youtube_queries": ["one", "two"]}}}
    r = await env.c.post("/api/campaigns/c1/generate", json=bad)
    assert r.status_code == 422 and "Your search needs changes" in r.json()["detail"]

"""Agent-written text over MCP (F9.6): the strategy checks, and the website never inherits agent mode."""

import pytest

from app.discovery import agent_ai
from app.discovery.brief import parse_brief, without_agent_mode
from tests.discovery.fakes import BRIEF, STRATEGY

brief = parse_brief(BRIEF)
GOOD = {**STRATEGY.model_dump(), "topics": ["a", "b", "c"], "youtube_queries": ["ml roadmap freshers", "data science career", "python for ai",
        "learn machine learning", "ai jobs india", "data analyst skills"]}


def test_a_well_formed_strategy_passes_the_code_rules():
    out, problems = agent_ai.clean(GOOD, brief)
    assert problems == [] and out["youtube_queries"][0] == "ml roadmap freshers"


@pytest.mark.parametrize("change,words", [
    ({"youtube_queries": ["one", "two words", "three words here", "four words in here", "five words in here ok", "six"]}, "2-5 words"),
    ({"youtube_queries": ["ml roadmap freshers"]}, "needs 6-12"),
    ({"youtube_queries": GOOD["youtube_queries"][:5] + ["datalaunch bootcamp review"]}, "brand name"),
    ({"x_queries": ["#ai tips"]}, "no hashtags"),
    ({"x_queries": ["a b c d"]}, "1-3 plain words"),
    ({"topics": ["only one"]}, "topics needs"),
    ({"competitors": list("abcdef")}, "at most 5"),
])
def test_each_code_rule_is_sent_back_in_plain_words(change, words):
    out, problems = agent_ai.clean({**GOOD, **change}, brief)
    assert out is None and any(words in p["check"] for p in problems)


def test_a_wrong_shape_is_explained_not_a_crash():
    out, problems = agent_ai.clean({"topics": "not a list"}, brief)
    assert out is None and problems


def test_the_hash_ignores_key_order():
    assert agent_ai.strategy_hash({"a": 1, "b": 2}) == agent_ai.strategy_hash({"b": 2, "a": 1})


def test_the_website_never_inherits_agent_mode():
    saved = {**BRIEF, "campaign": {**BRIEF["campaign"], "ai_mode": "agent", "agent_strategy": GOOD}, "agent_review": {"passed": True}}
    clean = without_agent_mode(saved)
    assert "agent_review" not in clean and "ai_mode" not in clean["campaign"] and "agent_strategy" not in clean["campaign"]
    assert clean["campaign"]["goal"] == BRIEF["campaign"]["goal"] and parse_brief(clean).ai_mode == "ours"
    assert parse_brief(saved).ai_mode == "agent"  # the saved details themselves are untouched

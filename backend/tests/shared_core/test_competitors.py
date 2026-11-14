"""Competitor promoted (roadmap F1.19): only sponsored posts naming a competitor count, and the campaign
chooses what that does (show / prefer / avoid). Code only."""

from app.discovery.brief import parse_brief
from app.judge import constants as K
from app.judge.combine import score_creator
from app.metrics.competitors import promotions
from tests.shared_core.test_judging import GOOD, judgment, metrics

POSTS = [
    {"text": "My new desk setup", "description": "This video is sponsored by Notion. Try it free."},
    {"text": "Notion vs Obsidian: honest review", "description": "Not sponsored, my own opinion."},
    {"text": "How I plan my week", "description": "Thanks to ClickUp for sponsoring this video!"},
    {"text": "Notion templates", "description": "#ad partnered with Notion"},
    {"text": "Notionally speaking about notes", "description": "sponsored by Acme"},
]


def test_only_sponsored_posts_naming_a_competitor_count():
    out = promotions(POSTS, ["Notion", "ClickUp", "Todoist"])
    assert out == [{"brand": "Notion", "posts": 2}, {"brand": "ClickUp", "posts": 1}]
    assert promotions(POSTS, []) == [] and promotions([], ["Notion"]) == []


def test_whole_words_only():
    assert promotions([{"text": "x", "description": "sponsored by Acme. #notion @notion notion.so"}], ["Notion"]) == []
    assert promotions([{"text": "x", "description": "sponsored by Click Up"}], ["ClickUp"]) == []
    assert promotions([{"text": "x", "description": "sponsored by Click-Up"}], ["Click Up"]) == [{"brand": "Click Up", "posts": 1}]


def test_the_campaign_chooses_what_it_does():
    promos = [{"brand": "Notion", "posts": 2}]
    show = score_creator(judgment(**GOOD), metrics(), competitor_promos=promos, competitor_mode="show")
    none = score_creator(judgment(**GOOD), metrics())
    prefer = score_creator(judgment(**GOOD), metrics(), competitor_promos=promos, competitor_mode="prefer")
    avoid = score_creator(judgment(**GOOD), metrics(), competitor_promos=promos, competitor_mode="avoid")
    assert show.final_score == none.final_score and "competitor" in show.flags and not show.dropped
    assert prefer.final_score > none.final_score and prefer.bonus >= K.COMPETITOR_BONUS
    assert avoid.dropped and "recently promoted a competitor (Notion)" in avoid.drop_reasons
    assert "competitor" not in none.flags


def test_brief_reads_competitors_and_keeps_cached_work():
    base = {"brand": {"name": "Lumen"}, "campaign": {}}
    with_rivals = {"brand": {"name": "Lumen"},
                   "campaign": {"competitors": [" Notion ", "notion", "Notion", "", "x" * 80, "ClickUp"], "competitor_mode": "avoid"}}
    b = parse_brief(with_rivals)
    assert b.competitors[0] == "Notion" and "ClickUp" in b.competitors and len(b.competitors[-2]) <= 60
    assert b.competitor_mode == "avoid"
    assert parse_brief({**base, "campaign": {"competitor_mode": "nonsense"}}).competitor_mode == "show"
    assert b.hash() == parse_brief(base).hash()  # same strategy and Jev answers are reused

"""LinkedIn adapter: replays real logged-out Apify (HarvestAPI) responses recorded on Nov 13 2026
(tests/fixtures/linkedin/*.json). No live API calls."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.metrics.compute import BriefContext, compute_metrics, passes_gates
from app.platforms.apify import ApifyError, MemoryStore
from app.platforms.base import CandidateRef, Limits, PlatformAdapter, Strategy
from app.platforms.linkedin import (
    MIN_FOLLOWERS,
    POSTS_ACTOR,
    PROFILE_ACTOR,
    SEARCH_ACTOR,
    LinkedInAdapter,
    _slug,
    item_to_post,
)

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "linkedin"
SEARCH = json.loads((FIX / "search.json").read_text())
PROFILES = json.loads((FIX / "profiles.json").read_text())
POSTS = json.loads((FIX / "profile_posts.json").read_text())
NOW = datetime(2026, 11, 13, 11, 0, tzinfo=timezone.utc)
LIMITS = Limits(max_queries=2, max_candidates=100, max_profiles=10, published_within_days=21)
STRATEGY = Strategy(topics=["devops"], pain_points=[], queries={"linkedin": ["devops"]})

pytestmark = pytest.mark.asyncio


class ReplayApify:
    def __init__(self, fail: dict | None = None):
        self.calls: list[tuple[str, dict, float]] = []
        self.fail = fail or {}

    async def run(self, actor, run_input, *, max_usd):
        self.calls.append((actor, run_input, max_usd))
        if actor in self.fail:
            raise self.fail[actor]
        if actor == SEARCH_ACTOR:
            return SEARCH
        if actor == PROFILE_ACTOR:
            wanted = {_slug(u) for u in run_input["queries"]}
            return [p for p in PROFILES if p["publicIdentifier"] in wanted]
        if actor == POSTS_ACTOR:
            wanted = {_slug(u) for u in run_input["targetUrls"]}
            return [p for p in POSTS if p["author"]["publicIdentifier"] in wanted]
        raise AssertionError(actor)


def adapter(api=None, store=None):
    return LinkedInAdapter(api or ReplayApify(), store=store or MemoryStore(), now=lambda: NOW)


def refs_for(ids):
    return [CandidateRef(platform="linkedin", platform_id=i, found_via="search") for i in ids]


async def test_adapter_shape():
    assert isinstance(adapter(), PlatformAdapter)


async def test_search_keeps_people_not_company_pages_ranked_by_engagement():
    api, store = ReplayApify(), MemoryStore()
    refs = await adapter(api, store).source_candidates(STRATEGY, LIMITS)
    people = {i["author"]["publicIdentifier"] for i in SEARCH if i["author"]["type"] == "profile"}
    assert {r.platform_id for r in refs} == people
    assert all(r.platform == "linkedin" for r in refs)
    # helenchukwukelu's post had 12 likes + 3 comments: the most engaging person ranks first
    assert refs[0].platform_id == "helenchukwukelu"
    [(actor, run_input, cap)] = api.calls
    assert actor == SEARCH_ACTOR and run_input["searchQueries"] == ["devops"] and run_input["postedLimit"] == "month"
    assert cap <= 0.15
    again = ReplayApify()
    assert [r.platform_id for r in await adapter(again, store).source_candidates(STRATEGY, LIMITS)] == \
        [r.platform_id for r in refs]
    assert not again.calls


async def test_profiles_filter_then_posts_only_for_survivors():
    api = ReplayApify()
    a = adapter(api)
    profiles = await a.fetch_profiles(refs_for(["helenchukwukelu", "rhacopian", "nobody-here"]),
                                      {"min_subscribers": 0}, max_deep=10)
    assert [p["platform_id"] for p in profiles] == ["helenchukwukelu"]
    assert a.dropped["rhacopian"] == "below the minimum follower count"  # 705 followers < MIN_FOLLOWERS
    assert a.dropped["nobody-here"] == "profile not found"
    assert [c[0] for c in api.calls] == [PROFILE_ACTOR, POSTS_ACTOR]
    assert api.calls[1][1]["targetUrls"] == ["https://www.linkedin.com/in/helenchukwukelu"]
    assert api.calls[1][1]["includeReposts"] is False

    helen = profiles[0]
    assert helen["followers"] > MIN_FOLLOWERS and helen["country"] == "GB"
    assert helen["url"] == "https://www.linkedin.com/in/helenchukwukelu/" and helen["avatar_url"]
    assert helen["cross_links"].get("youtube") or any("youtube.com" in u for u in helen["external_links"])
    assert len(helen["recent_posts"]) == 8 and all(p["views"] is None for p in helen["recent_posts"])
    assert helen["platform_stats"]["creator_mode"] is True


async def test_profiles_and_posts_are_cached():
    store = MemoryStore()
    await adapter(ReplayApify(), store).fetch_profiles(refs_for(["helenchukwukelu"]), {"min_subscribers": 0})
    again = ReplayApify()
    [p] = await adapter(again, store).fetch_profiles(refs_for(["helenchukwukelu"]), {"min_subscribers": 0})
    assert not again.calls and p["recent_posts"]


async def test_metrics_use_engagement_per_follower_and_the_tier_price():
    [p] = await adapter().fetch_profiles(refs_for(["helenchukwukelu"]), None)
    m = compute_metrics(p, BriefContext(), now=NOW)
    assert not m.has_public_views and m.engagement_rate and m.valuation and m.fair_low < m.fair_high
    ok, why = passes_gates(m, BriefContext())
    assert ok, why


async def test_out_of_credits_stops_and_warns_once():
    api = ReplayApify(fail={SEARCH_ACTOR: ApifyError(402, "Not enough usage"), PROFILE_ACTOR: ApifyError(402, "x")})
    a = adapter(api)
    assert await a.source_candidates(STRATEGY, LIMITS) == []
    assert await a.fetch_profiles(refs_for(["helenchukwukelu"]), {"min_subscribers": 0}) == []
    assert len(api.calls) == 1
    assert a.warnings == ["The LinkedIn data provider is out of credits, so LinkedIn results were cut short"]


async def test_posts_failure_keeps_profiles_with_a_warning():
    a = adapter(ReplayApify(fail={POSTS_ACTOR: ApifyError(500, "run failed")}))
    [p] = await a.fetch_profiles(refs_for(["helenchukwukelu"]), {"min_subscribers": 0})
    assert p["recent_posts"] == [] and any("posts failed" in w for w in a.warnings)
    assert not passes_gates(compute_metrics(p, BriefContext(), now=NOW), BriefContext())[0]  # no posts: not ranked


async def test_parsing():
    assert _slug("https://www.linkedin.com/in/Dreamless?miniProfileUrn=x") == "dreamless"
    assert _slug("helenchukwukelu") == "helenchukwukelu"
    post = item_to_post({"id": "1", "linkedinUrl": "u", "content": "hi", "postedAt": {"date": "2026-11-05T16:45:09.100Z"},
                         "engagement": {"likes": 3, "comments": -1, "shares": 2}, "postImages": [{"url": "img"}]})
    assert post["likes"] == 3 and post["comments"] == 0 and post["shares"] == 2 and post["format"] == "image"
    assert post["thumbnail_url"] == "img" and post["views"] is None and post["published_at"].day == 5


async def test_estimated_cost_of_a_full_search_is_under_the_target():
    from app.discovery.limits import LIMITS_BY_MODE

    assert adapter().estimate_cost_usd(LIMITS_BY_MODE["full"]) <= 3.0


async def test_free_plan_cap_keeps_partial_profiles_with_a_clear_warning():
    from app.platforms.apify import PLAN_LIMIT

    class Limited(ReplayApify):
        async def run(self, actor, run_input, *, max_usd):
            items = await super().run(actor, run_input, max_usd=max_usd)
            if actor == PROFILE_ACTOR:
                raise ApifyError(PLAN_LIMIT, "only some", items)
            return items

    a = adapter(Limited())
    [p] = await a.fetch_profiles(refs_for(["helenchukwukelu"]), {"min_subscribers": 0})
    assert p["recent_posts"]  # posts still fetched for the profile that came back
    assert a.warnings == ["The free Apify plan returns only a few LinkedIn results per run, so LinkedIn results were cut short"]

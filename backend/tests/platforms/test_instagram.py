"""Instagram adapter and Apify client: replays real Apify responses recorded on Nov 13 2026
(tests/fixtures/instagram/*.json). No live API calls."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from app.metrics.compute import BriefContext, compute_metrics, passes_gates
from app.platforms.apify import ApifyError, HttpApify, charged_usd, memory_memo
from app.platforms.base import CandidateRef, Limits, PlatformAdapter, Strategy
from app.platforms.instagram import (
    MAX_REEL_CREATORS,
    PROFILE_ACTOR,
    REEL_ACTOR,
    SEARCH_ACTOR,
    InstagramAdapter,
    MemoryStore,
    item_to_post,
    merge_posts,
)

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "instagram"
POPULAR = json.loads((FIX / "popular.json").read_text())
PROFILES = json.loads((FIX / "profiles.json").read_text())
REELS = json.loads((FIX / "reels.json").read_text())
NOW = datetime(2026, 11, 13, 11, 0, tzinfo=timezone.utc)
LIMITS = Limits(max_queries=2, max_candidates=100, max_profiles=10, published_within_days=21)
STRATEGY = Strategy(topics=["ai"], pain_points=[], queries={"instagram": ["ai tools"]})
RECORDED = {p["username"] for p in PROFILES}

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
            return POPULAR
        if actor == PROFILE_ACTOR:
            return [p for p in PROFILES if p["username"] in run_input["usernames"]]
        if actor == REEL_ACTOR:
            return [r for r in REELS if r["ownerUsername"] in run_input["username"]]
        return []  # hashtag fallback: nothing recorded


def adapter(api=None, store=None):
    return InstagramAdapter(api or ReplayApify(), store=store or MemoryStore(), now=lambda: NOW)


def refs_for(users):
    return [CandidateRef(platform="instagram", platform_id=u, found_via="search") for u in users]


async def test_adapter_shape():
    assert isinstance(adapter(), PlatformAdapter)


async def test_search_finds_reel_owners_in_one_run_and_caches_them():
    api, store = ReplayApify(), MemoryStore()
    refs = await adapter(api, store).source_candidates(STRATEGY, LIMITS)
    owners = {p["ownerUsername"].lower() for p in POPULAR}
    assert {r.platform_id for r in refs} == owners and all(r.platform == "instagram" for r in refs)
    [(actor, run_input, cap)] = api.calls
    assert actor == SEARCH_ACTOR and run_input["searchType"] == "popular" and run_input["search"] == "ai tools"
    assert cap < 0.1  # never more than the planned 20 results + margin
    again = ReplayApify()
    refs2 = await adapter(again, store).source_candidates(STRATEGY, LIMITS)
    assert not again.calls and [r.platform_id for r in refs2] == [r.platform_id for r in refs]


async def test_several_queries_share_one_run_and_map_back_by_query():
    api = ReplayApify()
    strategy = Strategy(topics=[], pain_points=[], queries={"instagram": ["ai tools", "#Prompt tips"]})
    await adapter(api).source_candidates(strategy, LIMITS)
    run_input = api.calls[0][1]
    assert run_input["search"] == "ai tools, Prompt tips"
    assert api.calls[1][1]["hashtags"] == ["prompttips"]  # nothing came back for it: one hashtag try


async def test_profiles_filter_then_reels_only_for_survivors():
    api = ReplayApify()
    a = adapter(api)
    users = ["opusjake", "heyypriyank", "mavgpt", "algorithmswithpeter", "missing_user"]
    profiles = await a.fetch_profiles(refs_for(users), {"min_subscribers": 10000, "max_subscribers": 1_000_000}, max_deep=10)
    got = {p["platform_id"] for p in profiles}
    assert got == {"opusjake", "heyypriyank", "algorithmswithpeter"}
    assert a.dropped["mavgpt"] == "above the maximum follower count"
    assert a.dropped["missing_user"] == "profile not found"
    actors = [c[0] for c in api.calls]
    assert actors == [PROFILE_ACTOR, REEL_ACTOR]  # one batch each
    assert set(api.calls[1][1]["username"]) == got

    jake = next(p for p in profiles if p["platform_id"] == "opusjake")
    assert jake["url"] == "https://www.instagram.com/opusjake/" and jake["followers"] > 100000 and jake["avatar_url"]
    views = [p["views"] for p in jake["recent_posts"] if p["views"] is not None]
    assert len(views) >= 5  # reel views merged in by shortcode
    assert all(p["published_at"] for p in jake["recent_posts"])
    assert jake["recent_posts"] == sorted(jake["recent_posts"], key=lambda p: p["published_at"], reverse=True)
    peter = next(p for p in profiles if p["platform_id"] == "algorithmswithpeter")
    assert "algorithmswithpeter@gmail.com" in peter["contacts"]["emails"]
    assert any("higgsfield.ai" in u for u in peter["external_links"])


async def test_profiles_and_reels_are_cached():
    store = MemoryStore()
    await adapter(ReplayApify(), store).fetch_profiles(refs_for(["opusjake"]), {"min_subscribers": 0}, max_deep=5)
    again = ReplayApify()
    [p] = await adapter(again, store).fetch_profiles(refs_for(["opusjake"]), {"min_subscribers": 0}, max_deep=5)
    assert not again.calls and p["recent_posts"]


async def test_reel_lookups_are_capped_per_run():
    a = adapter()
    users = [f"user{i}" for i in range(MAX_REEL_CREATORS + 5)]
    raw = {**PROFILES[0]}
    a._profiles = _fake_profiles(users, raw)
    seen = []

    async def reels(batch):
        seen.extend(batch)
        return {}
    a._reels = reels
    profiles = await a.fetch_profiles(refs_for(users), {"min_subscribers": 0}, max_deep=500)
    assert len(profiles) == MAX_REEL_CREATORS == len(seen)
    assert sum(1 for r in a.dropped.values() if r == "over the measuring limit for this run") == 5


def _fake_profiles(users, raw):
    async def profiles(batch):
        return {u: {**raw, "username": u} for u in batch}
    return profiles


async def test_out_of_credits_stops_and_warns_once():
    api = ReplayApify(fail={SEARCH_ACTOR: ApifyError(402, "Not enough usage"), PROFILE_ACTOR: ApifyError(402, "x")})
    a = adapter(api)
    assert await a.source_candidates(STRATEGY, LIMITS) == []
    assert await a.fetch_profiles(refs_for(["opusjake"]), {"min_subscribers": 0}) == []
    assert len(api.calls) == 1  # stopped after the first refusal
    assert a.warnings == ["The Instagram data provider is out of credits, so Instagram results were cut short"]


async def test_reel_failure_keeps_profiles_measured_on_likes():
    api = ReplayApify(fail={REEL_ACTOR: ApifyError(500, "run failed")})
    a = adapter(api)
    [p] = await a.fetch_profiles(refs_for(["heyypriyank"]), {"min_subscribers": 0}, max_deep=5)
    assert p["recent_posts"] and all(post["views"] is None for post in p["recent_posts"])
    assert any("reels failed" in w for w in a.warnings)
    m = compute_metrics(p, BriefContext(), now=NOW)
    assert not m.has_public_views and m.engagement_rate is not None


async def test_metrics_and_gates_work_on_instagram_profiles():
    profiles = await adapter().fetch_profiles(refs_for(["opusjake"]), None, max_deep=1)
    m = compute_metrics(profiles[0], BriefContext(), now=NOW)
    assert m.has_public_views and m.median_views and m.days_since_last_post is not None
    ok, why = passes_gates(m, BriefContext())
    assert ok, why


async def test_mostly_photo_creator_is_measured_per_follower_not_dropped_for_views():
    photos = [{"type": "Image", "shortCode": f"p{i}", "likesCount": 500, "commentsCount": 20,
               "timestamp": f"2026-11-{10 - i:02d}T10:00:00.000Z"} for i in range(8)]
    reel = [{"type": "Video", "shortCode": "r1", "likesCount": 50, "commentsCount": 2, "videoPlayCount": 900,
             "timestamp": "2026-11-11T10:00:00.000Z"}]
    p = adapter().profile_from({"username": "photog", "followersCount": 20000, "postsCount": 400,
                                "latestPosts": photos + reel})
    m = compute_metrics(p, BriefContext(), now=NOW)
    assert not m.has_public_views and m.engagement_rate == pytest.approx(520 / 20000)
    assert passes_gates(m, BriefContext())[0]


async def test_post_parsing():
    post = item_to_post({"type": "Video", "shortCode": "abc", "likesCount": -1, "commentsCount": 3,
                         "videoPlayCount": 1000, "videoViewCount": 400, "timestamp": "2026-11-11T12:48:37.000Z"})
    assert post["views"] == 1000 and post["likes"] == 0 and post["format"] == "reel" and post["is_short_form"]
    assert post["url"] == "https://www.instagram.com/p/abc/"
    assert item_to_post({"type": "Sidecar", "shortCode": "s"})["format"] == "carousel"
    assert item_to_post({"type": "Image", "shortCode": "i"})["views"] is None
    merged = merge_posts([{"type": "Video", "shortCode": "a", "likesCount": 5, "timestamp": "2026-11-01T00:00:00Z"},
                          {"type": "Image", "shortCode": "pin", "isPinned": True, "timestamp": "2020-01-01T00:00:00Z"}],
                         [{"type": "Video", "shortCode": "a", "videoPlayCount": 77, "timestamp": "2026-11-01T00:00:00Z"}])
    assert [p["post_id"] for p in merged] == ["a"] and merged[0]["views"] == 77 and merged[0]["likes"] == 5


async def test_estimated_cost_of_a_full_search_is_under_the_target():
    from app.discovery.limits import LIMITS_BY_MODE

    assert adapter().estimate_cost_usd(LIMITS_BY_MODE["full"]) <= 1.5


# --- Apify client: start, poll, read, cost, resume ---------------------------------------------


@pytest.fixture
def costs(monkeypatch):
    seen = []

    async def fake_record(record):
        seen.append(record)
    monkeypatch.setattr("app.platforms.apify.record_cost", fake_record)
    return seen


def apify_server(statuses, items, events):
    log = {"started": 0, "polls": 0}

    def handler(request: httpx.Request):
        assert request.headers["authorization"] == "Bearer test-token"
        path = request.url.path
        if request.method == "POST" and path.endswith("/runs"):
            log["started"] += 1
            log["cap"] = request.url.params["maxTotalChargeUsd"]
            return httpx.Response(201, json={"data": {"id": "run1", "status": "READY"}})
        if path.endswith("/actor-runs/run1"):
            status = statuses[min(log["polls"], len(statuses) - 1)]
            log["polls"] += 1
            return httpx.Response(200, json={"data": {"id": "run1", "status": status, "defaultDatasetId": "ds1",
                                                      "chargedEventCounts": events}})
        if path.endswith("/datasets/ds1/items"):
            return httpx.Response(200, json=items)
        return httpx.Response(404, text="nope")

    return handler, log


def client(handler, memo=None):
    return HttpApify("test-token", memo=memo or memory_memo(),
                     client=httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.test/v2"))


async def test_client_polls_until_done_and_logs_charged_cost(costs):
    handler, log = apify_server(["RUNNING", "SUCCEEDED"], [{"username": "a"}, {"error": "not found"}],
                                {"profile": 1})
    items = await client(handler).run(PROFILE_ACTOR, {"usernames": ["a", "b"]}, max_usd=0.0062)
    assert items == [{"username": "a"}] and log["polls"] == 2 and log["cap"] == "0.0062"
    assert costs[0].provider == "apify" and costs[0].usd == Decimal("0.0026") and costs[0].units == 1


async def test_a_retry_picks_up_the_same_run_instead_of_paying_again(costs):
    memo = memory_memo()
    handler, log = apify_server(["SUCCEEDED"], [{"username": "a"}], {"profile": 1})
    await client(handler, memo).run(PROFILE_ACTOR, {"usernames": ["a"]}, max_usd=0.01)
    await client(handler, memo).run(PROFILE_ACTOR, {"usernames": ["a"]}, max_usd=0.01)
    assert log["started"] == 1


async def test_failed_run_without_items_raises(costs):
    handler, _ = apify_server(["FAILED"], [], {})
    with pytest.raises(ApifyError):
        await client(handler).run(REEL_ACTOR, {"username": ["a"]}, max_usd=0.01)


async def test_charged_usd_uses_the_price_table():
    assert charged_usd(REEL_ACTOR, {"reel": 10, "actor-start": 1}) == Decimal("0.027")
    assert charged_usd("unknown/actor", {"x": 5}) == 0


async def test_missing_token_is_refused(monkeypatch):
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    monkeypatch.delenv("APIFY_API_TOKEN", raising=False)
    with pytest.raises(ApifyError):
        HttpApify()


async def test_queries_popular_search_misses_get_one_hashtag_try():
    from app.platforms.instagram import HASHTAG_ACTOR

    class Mixed(ReplayApify):
        async def run(self, actor, run_input, *, max_usd):
            self.calls.append((actor, run_input, max_usd))
            if actor == SEARCH_ACTOR:  # what Apify returns for a word popular search can't serve
                return [{**POPULAR[0], "inputUrl": "https://www.instagram.com/popular/ai-tools"},
                        {"inputUrl": "https://www.instagram.com/popular/home-workout", "error": "no_items"}]
            return [{"inputUrl": "https://www.instagram.com/explore/tags/homeworkout", "ownerUsername": "Vadimv.fit",
                     "type": "Video"}]

    api = Mixed()
    strategy = Strategy(topics=[], pain_points=[], queries={"instagram": ["ai tools", "home workout"]})
    refs = await adapter(api).source_candidates(strategy, LIMITS)
    assert [c[0] for c in api.calls] == [SEARCH_ACTOR, HASHTAG_ACTOR]
    assert api.calls[1][1]["hashtags"] == ["homeworkout"] and api.calls[1][1]["resultsType"] == "reels"
    assert {r.platform_id for r in refs} == {POPULAR[0]["ownerUsername"].lower(), "vadimv.fit"}


async def test_photo_heavy_creator_with_enough_reels_is_measured_on_reel_views():
    photos = [{"type": "Image", "shortCode": f"p{i}", "likesCount": 500, "commentsCount": 20,
               "timestamp": f"2026-11-{10 - i:02d}T10:00:00.000Z"} for i in range(8)]
    reels = [{"type": "Video", "shortCode": f"r{i}", "likesCount": 300, "commentsCount": 10,
              "videoPlayCount": 10000 + i * 1000, "timestamp": f"2026-11-{11 - i:02d}T12:00:00.000Z"} for i in range(4)]
    p = adapter().profile_from({"username": "mix", "followersCount": 50000, "postsCount": 400,
                                "latestPosts": photos + reels})
    m = compute_metrics(p, BriefContext(), now=NOW)
    assert m.has_public_views and m.posts_used == 4 and m.median_views == 11500

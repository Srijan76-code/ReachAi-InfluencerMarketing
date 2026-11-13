"""X adapter and client: replays real twitterapi.io responses recorded on Nov 13 2026
(tests/fixtures/x/*.json). No live API calls."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from app.metrics.compute import BriefContext, compute_metrics
from app.platforms.base import CandidateRef, Limits, PlatformAdapter, Strategy
from app.platforms.x import MIN_FAVES, XAdapter, parse_x_time, tweet_to_post
from app.platforms.x_api import HttpXAPI, XAPIError

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "x"
SEARCH = json.loads((FIX / "search_top.json").read_text())
TIMELINE = json.loads((FIX / "last_tweets.json").read_text())
NOW = datetime(2026, 11, 13, 9, 0, tzinfo=timezone.utc)
LIMITS = Limits(max_queries=2, max_candidates=100, max_profiles=5, published_within_days=21)
STRATEGY = Strategy(topics=["ai tools"], pain_points=[], queries={"x": ["ai coding assistant", "ai agents"]})

pytestmark = pytest.mark.asyncio


class ReplayAPI:
    def __init__(self, fail_after: int | None = None):
        self.calls: list[tuple] = []
        self.fail_after = fail_after

    def _maybe_fail(self):
        if self.fail_after is not None and len(self.calls) > self.fail_after:
            raise XAPIError(402, "Credits not enough")

    async def advanced_search(self, query, query_type="Top", cursor=None):
        self.calls.append(("search", query, cursor))
        self._maybe_fail()
        page = dict(SEARCH)
        if cursor:  # second page: same tweets, no more pages
            page = {**SEARCH, "has_next_page": False, "next_cursor": None}
        return page

    async def last_tweets(self, user_id, cursor=None):
        self.calls.append(("timeline", user_id, cursor))
        self._maybe_fail()
        data = json.loads(json.dumps(TIMELINE))
        for t in data["data"]["tweets"]:  # make the timeline belong to the asked user
            t.setdefault("author", {})["id"] = user_id
        return data

    async def user_info(self, user_name):
        raise AssertionError("not used")


async def no_cache(namespace, key, ttl, compute):
    return await compute(), False


def adapter(api=None):
    return XAdapter(api or ReplayAPI(), cache=no_cache, now=lambda: NOW)


async def test_adapter_shape():
    assert isinstance(adapter(), PlatformAdapter)


async def test_search_finds_unique_authors_with_filters_in_the_query():
    api = ReplayAPI()
    refs = await adapter(api).source_candidates(STRATEGY, LIMITS)
    authors = {t["author"]["id"] for t in SEARCH["tweets"]}
    assert {r.platform_id for r in refs} == authors and len(refs) == len(authors)
    assert all(r.platform == "x" and r.found_via == "search" for r in refs)
    queries = [c[1] for c in api.calls if c[0] == "search"]
    assert len(queries) == 4  # 2 queries x 2 pages
    assert all(f"min_faves:{MIN_FAVES}" in q and "-filter:replies" in q and "since_time:" in q for q in queries)


async def test_profiles_come_free_from_search_and_posts_skip_reposts():
    api = ReplayAPI()
    a = adapter(api)
    refs = await a.source_candidates(STRATEGY, LIMITS)
    profiles = await a.fetch_profiles(refs, {"min_subscribers": 10000, "max_subscribers": 300000}, max_deep=3)
    assert len(profiles) == 3  # max_deep
    assert all(10000 <= p["followers"] <= 300000 for p in profiles)
    assert any(r == "below the minimum follower count" for r in a.dropped.values())
    assert sum(1 for c in api.calls if c[0] == "timeline") == 3  # only survivors cost a timeline
    p = profiles[0]
    assert p["platform"] == "x" and p["url"].startswith("https://x.com/") and p["source"] == "twitterapi"
    assert p["avatar_url"] and "_400x400." in p["avatar_url"]
    reposts = sum(1 for t in TIMELINE["data"]["tweets"] if t.get("retweeted_tweet") or t.get("isReply"))
    assert len(p["recent_posts"]) == len(TIMELINE["data"]["tweets"]) - reposts
    post = p["recent_posts"][0]
    assert post["views"] is not None and post["likes"] >= 0 and post["shares"] is not None and post["published_at"]


async def test_creators_from_our_database_are_looked_up_through_their_timeline():
    api = ReplayAPI()
    a = adapter(api)
    ref = CandidateRef(platform="x", platform_id="12345", found_via="creator_db")
    profiles = await a.fetch_profiles([ref], {"min_subscribers": 0}, max_deep=5)
    assert len(profiles) == 1 and profiles[0]["platform_id"] == "12345" and profiles[0]["recent_posts"]


async def test_running_out_of_provider_credits_stops_calls_with_one_warning():
    api = ReplayAPI(fail_after=1)
    a = adapter(api)
    refs = await a.source_candidates(STRATEGY, LIMITS)
    assert refs  # the first page got through
    before = len(api.calls)
    await a.fetch_profiles(refs, {"min_subscribers": 0}, max_deep=5)
    assert len(api.calls) == before  # stopped: no timeline calls
    assert a.warnings.count("The X data provider is out of credits, so X results were cut short") == 1


async def test_metrics_work_on_x_profiles():
    a = adapter()
    refs = await a.source_candidates(STRATEGY, LIMITS)
    [p] = await a.fetch_profiles(refs[:1], None, max_deep=1)
    m = compute_metrics(p, BriefContext(), now=NOW)
    assert m.to_dict()  # views-based metrics compute without errors


async def test_tweet_parsing():
    assert parse_x_time("Mon Nov 09 17:07:24 +0000 2026") == datetime(2026, 11, 9, 17, 7, 24, tzinfo=timezone.utc)
    assert parse_x_time("bad") is None
    post = tweet_to_post({"id": "1", "text": "hi", "createdAt": "Mon Nov 09 17:07:24 +0000 2026", "viewCount": 10,
                          "likeCount": 2, "replyCount": 1, "retweetCount": 3, "quoteCount": 1,
                          "extendedEntities": {"media": [{"type": "video", "media_url_https": "https://img"}]}})
    assert post["shares"] == 4 and post["format"] == "video" and post["thumbnail_url"] == "https://img"


async def test_estimated_cost_of_a_full_search_is_under_a_dollar():
    from app.discovery.limits import LIMITS_BY_MODE

    assert adapter().estimate_cost_usd(LIMITS_BY_MODE["full"]) < 1.0


# --- HTTP client: cost logging, retries, errors -------------------------------------------------


@pytest.fixture
def costs(monkeypatch):
    seen = []

    async def fake_record(record):
        seen.append(record)
    monkeypatch.setattr("app.platforms.x_api.record_cost", fake_record)
    return seen


def client(handler):
    return HttpXAPI("test-key", client=httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.test"),
                    per_second=1000)


async def test_client_logs_cost_per_tweet_with_a_minimum(costs):
    def handler(request):
        assert request.headers["x-api-key"] == "test-key"
        if "advanced_search" in request.url.path:
            return httpx.Response(200, json={"tweets": [{"id": str(i)} for i in range(20)], "has_next_page": False})
        return httpx.Response(200, json={"status": "success", "data": {"tweets": []}})

    api = client(handler)
    await api.advanced_search("x")
    await api.last_tweets("1")
    assert [c.units for c in costs] == [20, 0]
    assert costs[0].usd == Decimal(300) / Decimal(100000) and costs[1].usd == Decimal(15) / Decimal(100000)
    assert all(c.provider == "twitterapi" for c in costs)


async def test_client_retries_rate_limits_and_reports_errors(costs, monkeypatch):
    async def no_sleep(_):
        return None
    monkeypatch.setattr("app.platforms.x_api.asyncio.sleep", no_sleep)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, text="slow down")
        if "last_tweets" in request.url.path:
            return httpx.Response(402, text="Credits not enough")
        return httpx.Response(200, json={"tweets": [], "has_next_page": False})

    api = client(handler)
    await api.advanced_search("x")  # 429 then 200
    with pytest.raises(XAPIError) as err:
        await api.last_tweets("1")
    assert err.value.out_of_credits and calls["n"] == 3


async def test_missing_key_is_refused(monkeypatch):
    monkeypatch.delenv("X_PROVIDER_API_KEY", raising=False)
    with pytest.raises(XAPIError):
        HttpXAPI()

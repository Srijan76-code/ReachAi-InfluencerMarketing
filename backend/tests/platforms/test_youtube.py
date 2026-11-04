"""YouTube adapter: replays a real recording (tests/fixtures/youtube/recording.json), plus
hand-built edge cases. No live API calls. Re-record with `python -m scripts.record_youtube_fixtures`."""

from collections import Counter
from datetime import datetime, timezone

import pytest

from app.metrics.compute import BriefContext, compute_metrics, passes_gates
from app.platforms.base import CandidateRef, Limits, PlatformAdapter, Strategy
from app.platforms.youtube import BATCH, YouTubeAdapter, extract_links
from app.platforms.youtube_api import HttpYouTubeAPI, YouTubeAPIError
from dataclasses import replace

from scripts.record_youtube_fixtures import CONSTRAINTS, LIMITS as RECORDED_LIMITS, RECORDED_AT, STRATEGY

# Every search result becomes a candidate: fused ranking puts channels found by both recorded searches
# first, and only 8 channels' details were recorded. Unrecorded ids are left out, like deleted channels.
LIMITS = replace(RECORDED_LIMITS, max_candidates=100)
from tests.platforms.youtube_replay import FIXTURE, ReplayAPI


async def no_cache(namespace, key, ttl, compute):
    return await compute(), False


def adapter(api=None):
    return YouTubeAdapter(api or ReplayAPI(), cache=no_cache, now=lambda: RECORDED_AT)


async def run_recorded():
    api = ReplayAPI()
    a = adapter(api)
    refs = await a.source_candidates(STRATEGY, LIMITS)
    profiles = await a.fetch_profiles(refs, CONSTRAINTS)
    return api, a, refs, profiles


# --- against the real recording -----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_replay_matches_every_recorded_call():
    api, a, refs, profiles = await run_recorded()
    assert api.misses == [] and a.warnings == []
    assert Counter(api.calls) == {"search": 2, "channels": 2, "playlistItems": 8, "videos": 3}  # 100 ids = 2 lookups
    assert len(profiles) == 8 and len(api.unrecorded) == len(refs) - 8


@pytest.mark.asyncio
async def test_candidates_mix_channel_and_trend_search():
    _, _, refs, _ = await run_recorded()
    vias = Counter(r.found_via for r in refs)
    assert vias["search"] > 0 and vias["trend_search"] > 0
    assert len({r.platform_id for r in refs}) == len(refs) <= LIMITS.max_candidates  # deduped across searches


@pytest.mark.asyncio
async def test_profiles_have_the_shared_shape():
    _, _, _, profiles = await run_recorded()
    assert profiles
    for p in profiles:
        assert p["platform"] == "youtube" and p["platform_id"].startswith("UC")
        assert p["display_name"] and p["followers"] > 0 and p["fetched_at"] == RECORDED_AT
        assert 0 < len(p["recent_posts"]) <= 15
        dates = [x["published_at"] for x in p["recent_posts"]]
        assert dates == sorted(dates, reverse=True)  # newest first
        for post in p["recent_posts"]:
            assert post["views"] is None or post["views"] >= 0
            assert isinstance(post["is_short_form"], bool) and post["url"].startswith("https://www.youtube.com/watch")
        assert p["platform_stats"]["uploads_playlist"]


@pytest.mark.asyncio
async def test_recorded_creators_flow_through_metrics_and_gates():
    _, _, _, profiles = await run_recorded()
    brief = BriefContext("edtech", "high")
    results = [passes_gates(compute_metrics(p, brief, now=RECORDED_AT), brief) for p in profiles]
    kept = [ok for ok, _ in results if ok]
    assert kept, "at least some real creators should pass the gates"
    reasons = {why for ok, why in results if not ok}
    assert all(isinstance(r, str) and r for r in reasons)


def test_fixture_has_no_real_email_addresses():
    import re

    emails = set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", FIXTURE.read_text()))
    assert emails <= {"hidden@example.com", "nhidden@example.com"}


# --- search planning ------------------------------------------------------------------------------------

def test_search_budget_split_between_channel_and_trend():
    a = adapter()
    s = Strategy(topics=[], pain_points=[], queries={"youtube": ["a", "b", "c", "d", "e"]})
    plan = a._plan_searches(s, Limits(max_queries=8))
    assert Counter(k for k, _ in plan) == {"channel": 5, "trend": 2}  # a quarter on trends; only 5 queries exist
    assert Counter(k for k, _ in a._plan_searches(s, Limits(max_queries=2))) == {"channel": 1, "trend": 1}  # at least one trend
    assert [k for k, _ in a._plan_searches(s, Limits(max_queries=1))] == ["channel"]
    no_trend = a._plan_searches(s, Limits(max_queries=4, published_within_days=None))
    assert [k for k, _ in no_trend] == ["channel"] * 4
    assert a._plan_searches(s, Limits(max_queries=0)) == []


def test_search_plan_dedupes_and_falls_back_to_topics():
    a = adapter()
    s = Strategy(topics=["ml careers"], pain_points=[], queries={"youtube": [" x ", "x", ""]})
    assert {q for _, q in a._plan_searches(s, Limits(max_queries=2))} == {"x"}
    fallback = a._plan_searches(Strategy(topics=["ml careers"], pain_points=[], queries={}), Limits(max_queries=2))
    assert {q for _, q in fallback} == {"ml careers"}


# --- failures --------------------------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["quotaExceeded", "rateLimitExceeded"])
async def test_quota_exhaustion_stops_searching_and_is_reported(reason):
    api = ReplayAPI(overrides={"search": YouTubeAPIError(403, reason)})
    a = adapter(api)
    refs = await a.source_candidates(Strategy(topics=[], pain_points=[], queries={"youtube": ["a", "b", "c"]}), Limits(max_queries=6))
    assert refs == [] and any("daily limit" in w for w in a.warnings)
    assert len(a.warnings) == 1  # one clear message, not one per search
    assert api.calls.count("search") <= 4  # the rest were skipped once the quota ran out (some run concurrently)


@pytest.mark.asyncio
async def test_one_failed_search_does_not_stop_the_others():
    calls = {"n": 0}

    class Flaky(ReplayAPI):
        async def search(self, **p):
            calls["n"] += 1
            if calls["n"] == 1:
                raise YouTubeAPIError(500, "backendError")
            return {"items": [{"snippet": {"channelId": f"UC{calls['n']}"}}]}

    a = adapter(Flaky())
    refs = await a.source_candidates(Strategy(topics=[], pain_points=[], queries={"youtube": ["a", "b"]}), Limits(max_queries=2, published_within_days=None))
    assert len(refs) == 1 and any("search failed" in w for w in a.warnings)


@pytest.mark.asyncio
async def test_failed_video_lookup_keeps_creator_without_posts():
    api, a, refs, _ = await run_recorded()
    broken = ReplayAPI(overrides={"videos": YouTubeAPIError(500, "backendError")})
    b = adapter(broken)
    profiles = await b.fetch_profiles(refs, CONSTRAINTS)
    assert profiles and all(p["recent_posts"] == [] for p in profiles)
    assert any("video details failed" in w for w in b.warnings)


# --- fetching edge cases -------------------------------------------------------------------------------

class Scripted:
    """Tiny fake API for hand-built cases."""

    def __init__(self, channels=None, uploads=None, videos=None):
        self._channels, self._uploads, self._videos = channels or [], uploads or {}, videos or {}
        self.channel_batches, self.video_batches = [], []

    async def search(self, **p):
        return {"items": []}

    async def channels(self, **p):
        ids = p["id"].split(",")
        self.channel_batches.append(len(ids))
        return {"items": [c for c in self._channels if c["id"] in ids]}

    async def playlist_items(self, **p):
        return {"items": [{"contentDetails": {"videoId": v}} for v in self._uploads.get(p["playlistId"], [])]}

    async def videos(self, **p):
        ids = p["id"].split(",")
        self.video_batches.append(len(ids))
        return {"items": [self._videos[v] for v in ids if v in self._videos]}


def channel(cid, subs=50_000, videos=100, views=1_000_000, country="IN", hidden=False, desc=""):
    stats = {"videoCount": str(videos), "viewCount": str(views)}
    if hidden:
        stats["hiddenSubscriberCount"] = True
    else:
        stats["subscriberCount"] = str(subs)
    return {
        "id": cid,
        "snippet": {"title": f"Channel {cid}", "description": desc, "country": country, "customUrl": f"@{cid.lower()}"},
        "statistics": stats,
        "contentDetails": {"relatedPlaylists": {"uploads": f"UU{cid}"}},
    }


def video(vid, views="1000", duration="PT10M", published="2026-10-20T10:00:00Z"):
    stats = {"likeCount": "50", "commentCount": "5"}
    if views is not None:
        stats["viewCount"] = views
    return {"id": vid, "snippet": {"title": f"Video {vid}", "publishedAt": published},
            "statistics": stats, "contentDetails": {"duration": duration}}


@pytest.mark.asyncio
async def test_cheap_filter_runs_before_spending_quota_on_videos():
    api = Scripted(
        channels=[channel("A"), channel("B", subs=500), channel("C", country="US"), channel("D", videos=2), channel("E", views=0)],
        uploads={"UUA": ["a1"], "UUB": ["b1"], "UUC": ["c1"]},
        videos={"a1": video("a1"), "b1": video("b1"), "c1": video("c1")},
    )
    a = adapter(api)
    refs = [CandidateRef("youtube", cid, "search") for cid in "ABCDE"]
    profiles = await a.fetch_profiles(refs, {"min_subscribers": 1000, "target_countries": ["in"]})
    assert [p["platform_id"] for p in profiles] == ["A"]
    assert set(a.dropped) == {"B", "C", "D", "E"}
    assert api.video_batches == [1]  # only A's video was looked up


@pytest.mark.asyncio
async def test_unknown_country_is_kept_and_hidden_subscribers_count_as_zero():
    api = Scripted(channels=[channel("A", country=""), channel("H", hidden=True)])
    a = adapter(api)
    profiles = await a.fetch_profiles([CandidateRef("youtube", "A", "search"), CandidateRef("youtube", "H", "search")],
                                      {"target_countries": ["IN"], "min_subscribers": 1000})
    assert [p["platform_id"] for p in profiles] == ["A"]
    assert a.dropped["H"] == "below the minimum subscriber count"


@pytest.mark.asyncio
async def test_large_requests_are_batched_in_fifties():
    ids = [f"C{i}" for i in range(120)]
    api = Scripted(
        channels=[channel(c) for c in ids],
        uploads={f"UU{c}": [f"{c}v{j}" for j in range(15)] for c in ids},
        videos={f"{c}v{j}": video(f"{c}v{j}") for c in ids for j in range(15)},
    )
    profiles = await adapter(api).fetch_profiles([CandidateRef("youtube", c, "search") for c in ids])
    assert len(profiles) == 120
    assert api.channel_batches == [BATCH, BATCH, 20]
    assert sum(api.video_batches) == 120 * 15 and max(api.video_batches) == BATCH
    assert len(api.video_batches) == 36  # 1,800 videos / 50 per call


@pytest.mark.asyncio
async def test_shorts_missing_views_and_bad_dates_are_handled():
    api = Scripted(
        channels=[channel("A")],
        uploads={"UUA": ["s", "l", "nv", "bad"]},
        videos={"s": video("s", duration="PT45S"), "l": video("l", duration="PT12M"),
                "nv": video("nv", views=None), "bad": video("bad", published="not-a-date", duration="garbage")},
    )
    [p] = await adapter(api).fetch_profiles([CandidateRef("youtube", "A", "search")])
    posts = {x["post_id"]: x for x in p["recent_posts"]}
    assert posts["s"]["is_short_form"] and not posts["l"]["is_short_form"]
    assert posts["nv"]["views"] is None
    assert posts["bad"]["published_at"] is None and posts["bad"]["is_short_form"] is False
    assert p["recent_posts"][-1]["post_id"] == "bad"  # undated posts sort last


@pytest.mark.asyncio
async def test_empty_and_foreign_refs():
    a = adapter(Scripted())
    assert await a.fetch_profiles([]) == []
    assert await a.fetch_profiles([CandidateRef("x", "123", "search")]) == []


@pytest.mark.asyncio
async def test_channel_without_uploads_has_no_posts():
    ch = channel("A")
    ch["contentDetails"] = {}
    [p] = await adapter(Scripted(channels=[ch])).fetch_profiles([CandidateRef("youtube", "A", "search")])
    assert p["recent_posts"] == []


# --- links ------------------------------------------------------------------------------------------------

def test_extract_links_from_channel_description():
    desc = (
        "Business: hi@creator.com.\nInsta: https://instagram.com/creator_x/ \n"
        "X: https://x.com/creatorx and https://twitter.com/intent/tweet?x=1\n"
        "https://www.linkedin.com/in/creator-x  https://www.tiktok.com/@creator.x\n"
        "Course: https://creator.com/course. Post: https://instagram.com/p/abc123"
    )
    emails, socials, others = extract_links(desc)
    assert emails == ["hi@creator.com"]
    assert socials == {
        "instagram": "https://instagram.com/creator_x",
        "x": "https://x.com/creatorx",
        "linkedin": "https://www.linkedin.com/in/creator-x",
        "tiktok": "https://www.tiktok.com/@creator.x",
    }
    assert "https://creator.com/course" in others
    assert extract_links("") == ([], {}, [])


# --- interface and estimates -------------------------------------------------------------------------------

def test_adapter_implements_the_interface_and_estimates_quota():
    a = adapter()
    assert isinstance(a, PlatformAdapter)
    assert a.estimate_cost_usd(Limits()) == 0.0
    q = YouTubeAdapter.estimate_quota(Limits(max_queries=8, max_profiles=150, max_candidates=300))
    assert 900 < q < 1100  # ~1,000 units for a default run
    assert a.priors().has_public_views


def test_http_client_needs_a_key(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    with pytest.raises(YouTubeAPIError):
        HttpYouTubeAPI()


def test_quota_error_detection():
    assert YouTubeAPIError(403, "quotaExceeded").quota_exceeded
    assert not YouTubeAPIError(403, "forbidden").quota_exceeded
    assert YouTubeAPIError(403, "rateLimitExceeded").quota_exceeded  # also sent once the daily search allowance is gone
    assert YouTubeAPIError(403, "dailyLimitExceeded").quota_exceeded
    assert not YouTubeAPIError(500, "quotaExceeded").quota_exceeded


# --- HTTP client ----------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_http_client_records_quota_and_parses_errors(cost_log):
    import httpx

    seen = []

    def handler(request: httpx.Request):
        seen.append(request.url)
        if request.url.path.endswith("/search"):
            return httpx.Response(403, json={"error": {"message": "quota", "errors": [{"reason": "quotaExceeded"}]}})
        return httpx.Response(200, json={"items": [{"id": "UC1"}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    api = HttpYouTubeAPI("secret-key", client=client)
    assert (await api.channels(part="snippet", id="UC1", regionCode=None))["items"][0]["id"] == "UC1"
    with pytest.raises(YouTubeAPIError) as err:
        await api.search(q="x")
    assert err.value.quota_exceeded
    assert api.units_used == 101  # failed calls still cost quota
    assert [r.units for r in cost_log] == [1, 100] and all(r.provider == "youtube" for r in cost_log)
    assert "regionCode" not in str(seen[0])  # None params are not sent
    assert all("secret-key" not in str(r) for r in cost_log)
    await api.aclose()


def test_top_up_plan_starts_with_unused_queries_and_wraps():
    a = adapter()
    s = Strategy(topics=[], pain_points=[], queries={"youtube": ["a", "b", "c", "d"]})
    lim = Limits(max_queries=3, published_within_days=None, query_offset=2, order="viewCount")
    assert a._plan_searches(s, lim) == [("video", "c"), ("video", "d"), ("video", "a")]
    # offset past the end: every query again (all-time and by views, so new results)
    assert [q for _, q in a._plan_searches(s, Limits(max_queries=2, query_offset=9, order="viewCount"))] == ["a", "b"]


@pytest.mark.asyncio
async def test_top_up_video_search_is_all_time_by_views_and_cached_separately():
    seen_params, keys = [], []

    class API:
        async def search(self, **p):
            seen_params.append(p)
            return {"items": [{"snippet": {"channelId": "UC1"}}]}

    async def cache(namespace, key, ttl, compute):
        keys.append(key)
        return await compute(), False

    a = YouTubeAdapter(API(), cache=cache, now=lambda: RECORDED_AT)
    hits = await a._search("video", "ml", Limits(order="viewCount"))
    await a._search("channel", "ml", Limits())
    assert hits == [("UC1", "video_search")]
    assert seen_params[0]["type"] == "video" and seen_params[0]["order"] == "viewCount"
    assert "publishedAfter" not in seen_params[0]
    assert keys[0]["order"] == "viewCount" and keys[0]["kind"] == "video" and "order" not in keys[1]


# --- fused ranking -------------------------------------------------------------------------------------

def test_fused_ranking_puts_channels_found_by_several_searches_first():
    from app.platforms.youtube import rank_fused

    results = [("q1", [("A", "search"), ("B", "search"), ("C", "search")]),
               ("q2", [("D", "trend_search"), ("C", "trend_search"), ("E", "trend_search")])]
    order = [r.platform_id for r in rank_fused(results, 10)]
    assert order[0] == "C"  # in both searches
    assert order[1:3] == ["A", "D"]  # then each search's top result, in search order
    assert set(order) == {"A", "B", "C", "D", "E"} and len(order) == 5
    c = rank_fused(results, 10)[0]
    assert c.found_via == "trend_search" and c.query == "q2"  # where it ranked best (rank 1 vs 2)
    assert [r.platform_id for r in rank_fused(results, 2)] == ["C", "A"]  # cap respected
    assert rank_fused([], 5) == [] and rank_fused([("q", [])], 5) == []


@pytest.mark.asyncio
async def test_cheap_check_covers_every_candidate_but_posts_only_for_the_best():
    """Subscriber counts for all candidates (1 unit per 50); posts only for the first `max_deep` that pass."""
    api = ReplayAPI()
    a = adapter(api)
    refs = await a.source_candidates(STRATEGY, LIMITS)
    profiles = await a.fetch_profiles(refs, CONSTRAINTS, max_deep=3)
    assert len(profiles) == 3 and api.calls.count("playlistItems") == 3
    assert api.calls.count("channels") == 2  # every candidate's channel info was checked
    over = [cid for cid, why in a.dropped.items() if why.startswith("over the measuring limit")]
    assert over  # passed the cheap check but weren't measured, and say so
    ranked = [r.platform_id for r in refs]
    assert [p["platform_id"] for p in profiles] == [c for c in ranked if c in {p["platform_id"] for p in profiles}]

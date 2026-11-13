"""YouTube on the shared pipeline (spec §4.8, roadmap F1.9).

Quota per run, with the defaults (8 searches, up to 150 profiles):
- searches: 8 × 100 = 800 units (half channel search, half recent-video "trend" search);
- channel info: 1 unit per 50 channels;
- uploads list: 1 unit per creator;
- video details: 1 unit per 50 videos, batched across creators (the old pipeline used one
  call per creator).
About 800 + 3 + 150 + 45 ≈ 1,000 units for 150 creators.
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Optional, Sequence

import isodate

from app.metrics import constants as MC
from app.platforms.base import CandidateRef, CreatorProfile, Limits, PlatformPriors, Post, Strategy
from app.platforms.links import extract_links  # noqa: F401  (re-exported for older imports)
from app.platforms.youtube_api import YouTubeAPI, YouTubeAPIError

logger = logging.getLogger(__name__)

# --- Settings ---------------------------------------------------------------------------------
TREND_SHARE = 0.25  # share of the search budget spent on recent-video (trend) search; niche trend searches return few results
QUOTA_WARNING = "YouTube's daily limit was reached (it resets at midnight Pacific time), so some searches or creators were skipped"
RRF_K = 60  # reciprocal rank fusion constant (the usual default)
SEARCH_RESULTS = 50  # max per search call (API limit)
POSTS_PER_CREATOR = 15
BATCH = 50  # max ids per channels.list / videos.list call
SEARCH_CONCURRENCY = 4
FETCH_CONCURRENCY = 20
SHORT_MAX_SECONDS = 180  # Shorts can be up to 3 minutes
MIN_VIDEOS = 5  # carried over from the old subscriber filter
SEARCH_CACHE_HOURS = 48

CacheFn = Callable[[str, Any, Optional[timedelta], Callable[[], Awaitable[Any]]], Awaitable[tuple[Any, bool]]]


async def _default_cache(namespace, key_parts, ttl, compute):
    from app.discovery.cache import cached

    return await cached(namespace, key_parts, ttl, compute)


def _chunks(items: Sequence[Any], size: int) -> list[list[Any]]:
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = isodate.parse_datetime(value)
    except (ValueError, isodate.ISO8601Error):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _duration_seconds(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return isodate.parse_duration(value).total_seconds()
    except (ValueError, isodate.ISO8601Error):
        return None


def _int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def rank_fused(results: list[tuple[str, list[tuple[str, str]]]], cap: int) -> list[CandidateRef]:
    """Merge several searches' results with reciprocal rank fusion: score = sum of 1 / (RRF_K + rank)
    over the searches a channel appears in. Channels several searches agree on come first; the top
    result of every search still ranks high, so no single search crowds out the others."""
    score: dict[str, float] = {}
    first: dict[str, tuple[int, int, str, str]] = {}  # cid -> (rank, search order, via, query)
    for order, (query, hits) in enumerate(results):
        for rank, (cid, via) in enumerate(hits):
            score[cid] = score.get(cid, 0.0) + 1.0 / (RRF_K + rank)
            if cid not in first or (rank, order) < first[cid][:2]:
                first[cid] = (rank, order, via, query)
    ordered = sorted(score, key=lambda c: (-score[c], first[c][0], first[c][1]))
    return [CandidateRef(platform="youtube", platform_id=c, found_via=first[c][2], query=first[c][3]) for c in ordered[:cap]]


def _thumbnail(snippet: dict) -> Optional[str]:
    """The channel's profile photo: 240px ("medium") if present, else the smallest one."""
    thumbs = snippet.get("thumbnails") or {}
    for size in ("medium", "high", "default"):
        url = (thumbs.get(size) or {}).get("url")
        if url:
            return url
    return None


class YouTubeAdapter:
    platform = "youtube"

    def __init__(self, api: YouTubeAPI, *, cache: Optional[CacheFn] = None, now: Optional[Callable[[], datetime]] = None):
        self.api = api
        self._cache = cache or _default_cache
        self._now = now or (lambda: datetime.now(timezone.utc))
        self.warnings: list[str] = []  # problems that didn't stop the run (shown in logs and run status)
        self.dropped: dict[str, str] = {}  # channel id -> reason dropped by cheap_filter
        self._quota_exhausted = False

    # --- Sourcing -------------------------------------------------------------------------------

    def _plan_searches(self, strategy: Strategy, limits: Limits) -> list[tuple[str, str]]:
        """Split the search budget: channel search on the top queries, plus recent-video
        ("trend") search on the top queries. Each search costs 100 quota units."""
        queries = [q.strip() for q in (strategy.queries.get("youtube") or strategy.topics) if q and q.strip()]
        queries = list(dict.fromkeys(queries))
        if queries and limits.query_offset:
            k = min(limits.query_offset, len(queries)) % len(queries)
            queries = queries[k:] + queries[:k]  # unused queries first, then the rest again
        budget = max(0, limits.max_queries)
        if limits.order:
            # Top-up round: all-time video search ordered by `order`. Video search returns full pages
            # where channel search on sentence-like queries often returns only a few channels.
            return [("video", q) for q in queries[:budget]]
        n_trend = max(1, math.floor(budget * TREND_SHARE)) if limits.published_within_days and budget >= 2 else 0  # at least one
        n_channel = budget - n_trend
        return [("channel", q) for q in queries[:n_channel]] + [("trend", q) for q in queries[:n_trend]]

    async def _search(self, kind: str, query: str, limits: Limits) -> list[tuple[str, str]]:
        """Returns [(channel_id, found_via)] for one search."""
        if self._quota_exhausted:
            return []
        params: dict[str, Any] = {"part": "snippet", "q": query, "maxResults": SEARCH_RESULTS, "regionCode": limits.region}
        if kind == "channel":
            params["type"] = "channel"
        elif kind == "video":
            params.update(type="video", order=limits.order or "relevance")
        else:
            after = self._now() - timedelta(days=limits.published_within_days or 21)
            params.update(type="video", order="viewCount", publishedAfter=after.strftime("%Y-%m-%dT00:00:00Z"))

        async def run():
            data = await self.api.search(**params)
            return [it.get("snippet", {}).get("channelId") or it.get("id", {}).get("channelId") for it in data.get("items", [])]

        key = {"platform": "youtube", "kind": kind, "q": query, "region": limits.region,
               "after": params.get("publishedAfter")}
        if kind == "video":
            key["order"] = params["order"]
        try:
            ids, _ = await self._cache("search", key, timedelta(hours=SEARCH_CACHE_HOURS), run)
        except YouTubeAPIError as exc:
            if exc.quota_exceeded:
                if not self._quota_exhausted:  # one message, even when parallel searches all fail
                    self.warnings.append(QUOTA_WARNING)
                self._quota_exhausted = True
            else:
                self.warnings.append(f"search failed for '{query}': {exc.reason}")
            return []
        via = {"channel": "search", "video": "video_search"}.get(kind, "trend_search")
        return [(cid, via) for cid in ids if cid]

    async def source_candidates(self, strategy: Strategy, limits: Limits) -> list[CandidateRef]:
        plan = self._plan_searches(strategy, limits)
        sem = asyncio.Semaphore(SEARCH_CONCURRENCY)

        async def one(kind, q):
            async with sem:
                return q, await self._search(kind, q, limits)

        results = await asyncio.gather(*(one(k, q) for k, q in plan))
        return rank_fused(results, limits.max_candidates)

    # --- Fetching -------------------------------------------------------------------------------

    async def fetch_avatars(self, channel_ids: list[str]) -> dict[str, str]:
        """Profile photos only: 1 quota unit per 50 channels (used to add photos to older results)."""
        out: dict[str, str] = {}
        ids = list(dict.fromkeys(channel_ids))
        for batch in _chunks(ids, BATCH):
            page = await self._safe(self.api.channels(part="snippet", id=",".join(batch), maxResults=BATCH), "photo lookup")
            for item in (page or {}).get("items", []):
                url = _thumbnail(item.get("snippet") or {})
                if url:
                    out[item["id"]] = url
            if self._quota_exhausted:
                break
        return out

    def _channel_to_profile(self, item: dict) -> CreatorProfile:
        snip, stats = item.get("snippet", {}), item.get("statistics", {})
        description = snip.get("description", "") or ""
        emails, socials, others = extract_links(description)
        handle = snip.get("customUrl")
        return CreatorProfile(
            platform="youtube",
            platform_id=item["id"],
            handle=handle,
            display_name=snip.get("title", ""),
            bio=description,
            url=f"https://www.youtube.com/{handle}" if handle else f"https://www.youtube.com/channel/{item['id']}",
            avatar_url=_thumbnail(snip),
            followers=0 if stats.get("hiddenSubscriberCount") else (_int(stats.get("subscriberCount")) or 0),
            country=(snip.get("country") or None),
            language=snip.get("defaultLanguage"),
            external_links=others,
            contacts={"emails": emails},
            cross_links=socials,
            recent_posts=[],
            platform_stats={
                "video_count": _int(stats.get("videoCount")) or 0,
                "lifetime_views": _int(stats.get("viewCount")) or 0,
                "uploads_playlist": item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads"),
                "subscribers_hidden": bool(stats.get("hiddenSubscriberCount")),
            },
            fetched_at=self._now(),
            source="youtube_api",
        )

    @staticmethod
    def _video_to_post(item: dict) -> Post:
        snip, stats = item.get("snippet", {}), item.get("statistics", {})
        seconds = _duration_seconds(item.get("contentDetails", {}).get("duration"))
        return Post(
            post_id=item["id"],
            url=f"https://www.youtube.com/watch?v={item['id']}",
            text=snip.get("title", ""),
            description=snip.get("description", "") or "",
            published_at=_parse_dt(snip.get("publishedAt")),
            views=_int(stats.get("viewCount")),
            likes=_int(stats.get("likeCount")) or 0,
            comments=_int(stats.get("commentCount")) or 0,
            shares=None,
            is_short_form=seconds is not None and seconds <= SHORT_MAX_SECONDS,
            thumbnail_url=_thumbnail(snip) or f"https://i.ytimg.com/vi/{item['id']}/mqdefault.jpg",
            format="short" if seconds is not None and seconds <= SHORT_MAX_SECONDS else "long",
        )

    async def _safe(self, coro, what: str):
        try:
            return await coro
        except YouTubeAPIError as exc:
            if exc.quota_exceeded:
                if not self._quota_exhausted:
                    self.warnings.append(QUOTA_WARNING)
                self._quota_exhausted = True
            else:
                self.warnings.append(f"{what} failed: {exc.reason}")
            return None

    async def fetch_profiles(self, refs: list[CandidateRef], constraints: Optional[dict] = None,
                             max_deep: Optional[int] = None) -> list[CreatorProfile]:
        """Channel info for every ref (1 unit per 50), then the cheap filter, then recent videos
        (about 1 unit per creator) for at most `max_deep` survivors, in the order given."""
        ids = list(dict.fromkeys(r.platform_id for r in refs if r.platform == "youtube"))
        if not ids:
            return []
        sem = asyncio.Semaphore(FETCH_CONCURRENCY)

        async def limited(coro):
            async with sem:
                return await coro

        # 1. channel info (cheap): 1 unit per 50 channels
        channel_pages = await asyncio.gather(*(
            limited(self._safe(self.api.channels(part="snippet,statistics,contentDetails", id=",".join(batch), maxResults=BATCH), "channel lookup"))
            for batch in _chunks(ids, BATCH)
        ))
        by_id: dict[str, CreatorProfile] = {}
        for page in channel_pages:
            for item in (page or {}).get("items", []):
                by_id[item["id"]] = self._channel_to_profile(item)

        # 2. cheap filter before spending more quota
        survivors: list[CreatorProfile] = []
        for cid in ids:
            p = by_id.get(cid)
            if p is None:
                continue
            if constraints is not None:
                ok, reason = self.cheap_filter(p, constraints)
                if not ok:
                    self.dropped[cid] = reason or "filtered"
                    continue
            survivors.append(p)
        if max_deep is not None and len(survivors) > max_deep:
            for p in survivors[max_deep:]:
                self.dropped[p["platform_id"]] = "over the measuring limit for this run"
            survivors = survivors[:max_deep]

        # 3. latest uploads per creator: 1 unit each
        async def uploads(p: CreatorProfile) -> list[str]:
            playlist = (p.get("platform_stats") or {}).get("uploads_playlist")
            if not playlist:
                return []
            page = await limited(self._safe(
                self.api.playlist_items(part="contentDetails", playlistId=playlist, maxResults=POSTS_PER_CREATOR),
                f"uploads for {p['platform_id']}",
            ))
            return [it.get("contentDetails", {}).get("videoId") for it in (page or {}).get("items", []) if it.get("contentDetails", {}).get("videoId")]

        video_ids_per_creator = await asyncio.gather(*(uploads(p) for p in survivors))

        # 4. video details, batched across creators: 1 unit per 50 videos
        all_video_ids = list(dict.fromkeys(v for vids in video_ids_per_creator for v in vids))
        video_pages = await asyncio.gather(*(
            limited(self._safe(self.api.videos(part="snippet,statistics,contentDetails", id=",".join(batch), maxResults=BATCH), "video details"))
            for batch in _chunks(all_video_ids, BATCH)
        ))
        posts_by_video = {item["id"]: self._video_to_post(item) for page in video_pages for item in (page or {}).get("items", [])}

        for profile, vids in zip(survivors, video_ids_per_creator):
            posts = [posts_by_video[v] for v in vids if v in posts_by_video]
            posts.sort(key=lambda p: p.get("published_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
            profile["recent_posts"] = posts
        return survivors

    # --- Rules and estimates ------------------------------------------------------------------------

    def cheap_filter(self, profile: CreatorProfile, constraints: dict) -> tuple[bool, Optional[str]]:
        followers = profile.get("followers") or 0
        stats = profile.get("platform_stats") or {}
        min_s, max_s = constraints.get("min_subscribers"), constraints.get("max_subscribers")
        if min_s is not None and followers < min_s:
            return False, "below the minimum subscriber count"
        if max_s is not None and followers > max_s:
            return False, "above the maximum subscriber count"
        targets = {c.upper() for c in constraints.get("target_countries") or []}
        country = (profile.get("country") or "").upper()
        if targets and country and country not in targets:  # unknown country is kept, not dropped
            return False, "outside the target countries"
        if stats.get("video_count", 0) < constraints.get("min_videos", MIN_VIDEOS):
            return False, "too few videos"
        if stats.get("lifetime_views", 0) <= 0:
            return False, "no views"
        return True, None

    def priors(self) -> PlatformPriors:
        return PlatformPriors(
            has_public_views=True,
            median_engagement_by_tier=MC.ENGAGEMENT_PRIOR["youtube"],
            ctr=MC.CTR_BY_INDUSTRY["other"],
        )

    def estimate_cost_usd(self, limits: Limits) -> float:
        return 0.0  # free in money; limited by quota (see estimate_quota)

    @staticmethod
    def estimate_quota(limits: Limits) -> int:
        profiles = limits.max_profiles
        return (
            limits.max_queries * 100
            + math.ceil(min(limits.max_candidates, profiles * 2) / BATCH)
            + profiles
            + math.ceil(profiles * POSTS_PER_CREATOR / BATCH)
        )

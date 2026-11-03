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
from app.platforms.youtube_api import YouTubeAPI, YouTubeAPIError

logger = logging.getLogger(__name__)

# --- Settings ---------------------------------------------------------------------------------
TREND_SHARE = 0.5  # share of the search budget spent on recent-video (trend) search
SEARCH_RESULTS = 50  # max per search call (API limit)
POSTS_PER_CREATOR = 15
BATCH = 50  # max ids per channels.list / videos.list call
SEARCH_CONCURRENCY = 4
FETCH_CONCURRENCY = 20
SHORT_MAX_SECONDS = 180  # Shorts can be up to 3 minutes
MIN_VIDEOS = 5  # carried over from the old subscriber filter
SEARCH_CACHE_HOURS = 48

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
URL = re.compile(r"https?://[^\s<>\"')\]]+", re.I)
SOCIAL_PATTERNS = {
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/(?!p/|reel/|reels/|explore/|stories/)([A-Za-z0-9_.]+)", re.I),
    "x": re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/(?!intent/|share|hashtag/|search)([A-Za-z0-9_]+)", re.I),
    "linkedin": re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/([A-Za-z0-9_\-%]+)", re.I),
    "tiktok": re.compile(r"https?://(?:www\.)?tiktok\.com/@([A-Za-z0-9_.]+)", re.I),
}

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


def extract_links(text: str) -> tuple[list[str], dict[str, str], list[str]]:
    """(emails, social links by platform, other links) found in a channel description."""
    text = text or ""
    emails = list(dict.fromkeys(e.rstrip(".") for e in EMAIL.findall(text)))
    socials: dict[str, str] = {}
    for name, pattern in SOCIAL_PATTERNS.items():
        m = pattern.search(text)
        if m:
            socials[name] = m.group(0).rstrip("/.")
    social_urls = set(socials.values())
    others = [u.rstrip("/.") for u in URL.findall(text)]
    others = [u for u in dict.fromkeys(others) if not any(u.startswith(s) for s in social_urls)]
    return emails, socials, others


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
        budget = max(0, limits.max_queries)
        n_trend = math.floor(budget * TREND_SHARE) if limits.published_within_days else 0
        n_channel = budget - n_trend
        return [("channel", q) for q in queries[:n_channel]] + [("trend", q) for q in queries[:n_trend]]

    async def _search(self, kind: str, query: str, limits: Limits) -> list[tuple[str, str]]:
        """Returns [(channel_id, found_via)] for one search."""
        if self._quota_exhausted:
            return []
        params: dict[str, Any] = {"part": "snippet", "q": query, "maxResults": SEARCH_RESULTS, "regionCode": limits.region}
        if kind == "channel":
            params["type"] = "channel"
        else:
            after = self._now() - timedelta(days=limits.published_within_days or 21)
            params.update(type="video", order="viewCount", publishedAfter=after.strftime("%Y-%m-%dT00:00:00Z"))

        async def run():
            data = await self.api.search(**params)
            return [it.get("snippet", {}).get("channelId") or it.get("id", {}).get("channelId") for it in data.get("items", [])]

        key = {"platform": "youtube", "kind": kind, "q": query, "region": limits.region,
               "after": params.get("publishedAfter")}
        try:
            ids, _ = await self._cache("search", key, timedelta(hours=SEARCH_CACHE_HOURS), run)
        except YouTubeAPIError as exc:
            if exc.quota_exceeded:
                self._quota_exhausted = True
                self.warnings.append("YouTube daily quota reached; some searches were skipped")
            else:
                self.warnings.append(f"search failed for '{query}': {exc.reason}")
            return []
        via = "search" if kind == "channel" else "trend_search"
        return [(cid, via) for cid in ids if cid]

    async def source_candidates(self, strategy: Strategy, limits: Limits) -> list[CandidateRef]:
        plan = self._plan_searches(strategy, limits)
        sem = asyncio.Semaphore(SEARCH_CONCURRENCY)

        async def one(kind, q):
            async with sem:
                return q, await self._search(kind, q, limits)

        results = await asyncio.gather(*(one(k, q) for k, q in plan))
        # Take results round-robin across searches, so the candidate cap doesn't keep only the
        # first search's results (trend results would otherwise never make it in).
        refs: dict[str, CandidateRef] = {}
        longest = max((len(hits) for _, hits in results), default=0)
        for rank in range(longest):
            for query, hits in results:
                if rank < len(hits):
                    cid, via = hits[rank]
                    if cid not in refs:
                        refs[cid] = CandidateRef(platform="youtube", platform_id=cid, found_via=via, query=query)
        return list(refs.values())[: limits.max_candidates]

    # --- Fetching -------------------------------------------------------------------------------

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
        )

    async def _safe(self, coro, what: str):
        try:
            return await coro
        except YouTubeAPIError as exc:
            if exc.quota_exceeded:
                self._quota_exhausted = True
                self.warnings.append("YouTube daily quota reached; some creators weren't fetched")
            else:
                self.warnings.append(f"{what} failed: {exc.reason}")
            return None

    async def fetch_profiles(self, refs: list[CandidateRef], constraints: Optional[dict] = None) -> list[CreatorProfile]:
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

"""Instagram on the shared pipeline (spec §6.2, roadmap F4.1), through Apify's official actors.

Three actor runs per search, each a single batch (spec §4.15 rule 5):
1. popular reels for the strategy's Instagram searches (instagram-search-scraper, "popular") → owners.
   Popular search finds nothing for some broad words ("fitness", "skincare"); those queries get one
   more try as hashtag reels (instagram-hashtag-scraper);
2. profiles for those owners (instagram-profile-scraper): followers, bio, links and the last 12 posts
   with likes and comments. This is the cheap filter's data: there is no free profile on Instagram;
3. recent reels with view counts (instagram-reel-scraper) for the best creators that pass the filter.

Cost with the defaults, at Apify's free-tier prices (≈ $2.60–2.70 per 1,000 results):
6 searches × 20 = 120 results ≈ $0.32 · 120 profiles ≈ $0.31 · 40 creators × 6 reels ≈ $0.63.
About $1.25 per full search, under the spec's $1.50 target. Profiles and reels are cached for 7 and
3 days, so a "Find more" or a second campaign in the same niche costs much less.
"""

from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Optional, Protocol

from app.metrics import constants as MC
from app.platforms.apify import PRICES, ApifyAPI, ApifyError
from app.platforms.base import CandidateRef, CreatorProfile, Limits, PlatformPriors, Post, Strategy
from app.platforms.links import extract_links
from app.platforms.youtube import rank_fused

logger = logging.getLogger(__name__)

# --- Settings ---------------------------------------------------------------------------------
SEARCH_ACTOR = "apify/instagram-search-scraper"
HASHTAG_ACTOR = "apify/instagram-hashtag-scraper"
PROFILE_ACTOR = "apify/instagram-profile-scraper"
REEL_ACTOR = "apify/instagram-reel-scraper"

MAX_QUERIES = 6
RESULTS_PER_QUERY = 20
MAX_PROFILE_LOOKUPS = 120  # profiles bought per search (the cheap filter needs them)
MAX_REEL_CREATORS = 40  # creators whose reels (with views) are bought per search
REELS_PER_CREATOR = 6
MIN_POSTS = 30  # accounts with fewer lifetime posts are too new or inactive
MAX_RECENT_POSTS = 20

SEARCH_CACHE = timedelta(hours=24)
PROFILE_CACHE = timedelta(days=7)
REEL_CACHE = timedelta(days=3)
CHARGE_MARGIN = 1.2  # a run's spending cap is its planned cost plus 20%

OUT_OF_CREDITS = "The Instagram data provider is out of credits, so Instagram results were cut short"
NO_VIEWS = "View counts for Instagram reels couldn't be loaded, so creators were measured on likes and comments"


class Store(Protocol):
    async def get(self, namespace: str, key: Any) -> Any: ...

    async def set(self, namespace: str, key: Any, value: Any, ttl: timedelta) -> None: ...


class DbStore:
    """The shared Postgres cache (spec §4.14)."""

    def __init__(self, session_factory_getter: Callable[[], Any] = lambda: None):
        self._sf = session_factory_getter

    async def get(self, namespace, key):
        from app.discovery.cache import cache_key, get_cached

        return await get_cached(namespace, cache_key(key), session_factory=self._sf())

    async def set(self, namespace, key, value, ttl):
        from app.discovery.cache import cache_key, set_cached

        await set_cached(namespace, cache_key(key), value, ttl, session_factory=self._sf())


class MemoryStore:
    def __init__(self):
        self.data: dict[tuple[str, str], Any] = {}

    async def get(self, namespace, key):
        return self.data.get((namespace, repr(key)))

    async def set(self, namespace, key, value, ttl):
        self.data[(namespace, repr(key))] = value


# --- Parsing ------------------------------------------------------------------------------------


def parse_ig_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _slug(query: str) -> str:
    """How the search actor writes a query into each result's inputUrl (".../popular/ai-tools")."""
    return re.sub(r"\s+", "-", query.strip().lower())


def _tag(query: str) -> str:
    return re.sub(r"[^a-z0-9_]", "", query.lower())


def _owners_by_query(items: list[dict], by_key: dict[str, str], key_of: Callable[[str], str]) -> dict[str, list[str]]:
    """Reel owners per query, in result order. Results say which query they came from in inputUrl."""
    out: dict[str, list[str]] = {q: [] for q in by_key.values()}
    only = next(iter(out)) if len(out) == 1 else None
    for item in items:
        last = (item.get("inputUrl") or "").rstrip("/").rsplit("/", 1)[-1].lower()
        q = by_key.get(key_of(last)) or only
        user = (item.get("ownerUsername") or "").lower()
        if q and user and not item.get("error"):
            out[q].append(user)
    return {q: list(dict.fromkeys(users)) for q, users in out.items()}


def item_to_post(item: dict) -> Post:
    kind = item.get("type")
    is_video = kind == "Video"
    views = _int(item.get("videoPlayCount")) if is_video else None
    if is_video and views is None:
        views = _int(item.get("videoViewCount"))
    fmt = "reel" if is_video else "carousel" if kind == "Sidecar" else "image"
    code = item.get("shortCode") or ""
    return Post(
        post_id=code or str(item.get("id") or ""),
        url=item.get("url") or (f"https://www.instagram.com/p/{code}/" if code else ""),
        text=(item.get("caption") or "")[:1000],
        description="",
        published_at=parse_ig_time(item.get("timestamp")),
        views=views,
        likes=max(0, _int(item.get("likesCount")) or 0),  # hidden like counts come back as -1
        comments=max(0, _int(item.get("commentsCount")) or 0),
        shares=None,
        is_short_form=is_video,
        thumbnail_url=item.get("displayUrl"),
        format=fmt,
    )


def merge_posts(latest: list[dict], reels: list[dict]) -> list[Post]:
    """The profile's last posts (likes, comments) with view counts from the reel scraper, newest first.
    Pinned posts are left out: they are old and not what the creator posts now."""
    by_code: dict[str, dict] = {}
    for item in latest:
        if item.get("isPinned"):
            continue
        by_code[item.get("shortCode") or str(item.get("id"))] = dict(item)
    for reel in reels:
        if reel.get("isPinned"):
            continue
        code = reel.get("shortCode") or str(reel.get("id"))
        merged = by_code.get(code, {})
        by_code[code] = {**merged, **{k: v for k, v in reel.items() if v is not None}}
    posts = [item_to_post(i) for i in by_code.values()]
    posts.sort(key=lambda p: p.get("published_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return posts[:MAX_RECENT_POSTS]


# Only what profiles and metrics need is cached, so cache rows stay small.
_POST_FIELDS = ("id", "type", "shortCode", "caption", "url", "commentsCount", "likesCount", "timestamp",
                "isPinned", "displayUrl", "videoViewCount", "videoPlayCount", "paidPartnership")
_PROFILE_FIELDS = ("id", "username", "fullName", "biography", "externalUrl", "externalUrls", "followersCount",
                   "followsCount", "postsCount", "verified", "private", "isBusinessAccount", "businessCategoryName",
                   "profilePicUrl", "profilePicUrlHD", "url")


def _slim_post(item: dict) -> dict:
    out = {k: item.get(k) for k in _POST_FIELDS if item.get(k) is not None}
    if isinstance(out.get("caption"), str):
        out["caption"] = out["caption"][:1000]
    return out


def _slim_profile(item: dict) -> dict:
    out = {k: item.get(k) for k in _PROFILE_FIELDS if item.get(k) is not None}
    out["externalUrls"] = [{"url": u.get("url"), "title": u.get("title")} for u in item.get("externalUrls") or []
                           if isinstance(u, dict) and u.get("url")]
    out["latestPosts"] = [_slim_post(p) for p in item.get("latestPosts") or [] if isinstance(p, dict)]
    return out


class InstagramAdapter:
    platform = "instagram"

    def __init__(self, api: ApifyAPI, *, store: Optional[Store] = None, now: Optional[Callable[[], datetime]] = None):
        self.api = api
        self.store = store or DbStore()
        self._now = now or (lambda: datetime.now(timezone.utc))
        self.warnings: list[str] = []
        self.dropped: dict[str, str] = {}
        self._stopped = False

    def _warn(self, text: str) -> None:
        if text not in self.warnings:
            self.warnings.append(text)

    def _failed(self, exc: ApifyError, what: str) -> None:
        if exc.out_of_credits:
            self._stopped = True
            self._warn(OUT_OF_CREDITS)
        else:
            self._warn(f"{what} failed: {exc.reason[:80]}")

    async def _run(self, actor: str, run_input: dict, planned_items: int, what: str) -> Optional[list[dict]]:
        if self._stopped or planned_items <= 0:
            return None
        price = max(PRICES.get(actor, {"x": 0.003}).values())
        cap = round(max(0.01, planned_items * price * CHARGE_MARGIN + 0.002), 4)
        try:
            return await self.api.run(actor, run_input, max_usd=cap)
        except ApifyError as exc:
            self._failed(exc, what)
            return None

    # --- Sourcing -------------------------------------------------------------------------------

    def _queries(self, strategy: Strategy, limits: Limits) -> list[str]:
        raw = strategy.queries.get("instagram") or strategy.topics
        queries = [re.sub(r"[#,]", " ", q).strip() for q in raw if q and q.strip()]
        queries = list(dict.fromkeys(q for q in queries if q))
        if queries and limits.query_offset:
            k = min(limits.query_offset, len(queries)) % len(queries)
            queries = queries[k:] + queries[:k]
        return queries[: max(0, min(limits.max_queries, MAX_QUERIES))]

    async def source_candidates(self, strategy: Strategy, limits: Limits) -> list[CandidateRef]:
        queries = self._queries(strategy, limits)
        found: dict[str, list[str]] = {}
        missing = []
        for q in queries:
            hit = await self.store.get("search", {"platform": "instagram", "q": q.lower()})
            if hit is None:
                missing.append(q)
            else:
                found[q] = hit
        if missing:
            items = await self._run(SEARCH_ACTOR, {"search": ", ".join(missing), "searchType": "popular",
                                                   "searchLimit": RESULTS_PER_QUERY},
                                    len(missing) * RESULTS_PER_QUERY, "Instagram search")
            per_query = _owners_by_query(items or [], {_slug(q): q for q in missing}, lambda s: s)
            empty = [q for q in missing if not per_query.get(q) and _tag(q)]
            if empty and items is not None:
                tags = {_tag(q): q for q in empty}
                more = await self._run(HASHTAG_ACTOR, {"hashtags": list(tags), "resultsType": "reels",
                                                       "resultsLimit": RESULTS_PER_QUERY},
                                       len(tags) * RESULTS_PER_QUERY, "Instagram hashtag search")
                per_query.update(_owners_by_query(more or [], tags, _tag))
            for q, users in per_query.items():
                found[q] = users
                if users:
                    await self.store.set("search", {"platform": "instagram", "q": q.lower()}, users, SEARCH_CACHE)
        results = [(q, [(u, "search") for u in found.get(q, [])]) for q in queries]
        refs = rank_fused(results, limits.max_candidates)
        return [CandidateRef(platform="instagram", platform_id=r.platform_id, found_via=r.found_via, query=r.query)
                for r in refs]

    # --- Fetching -------------------------------------------------------------------------------

    async def _cached_batch(self, namespace: str, users: list[str], ttl: timedelta,
                            fetch: Callable[[list[str]], Awaitable[Optional[dict[str, Any]]]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        missing = []
        for u in users:
            hit = await self.store.get(namespace, u)
            if hit is None:
                missing.append(u)
            else:
                out[u] = hit
        if missing:
            fresh = await fetch(missing) or {}
            for u, value in fresh.items():
                out[u] = value
                await self.store.set(namespace, u, value, ttl)
        return out

    async def _profiles(self, users: list[str]) -> dict[str, dict]:
        async def fetch(batch: list[str]) -> Optional[dict[str, dict]]:
            items = await self._run(PROFILE_ACTOR, {"usernames": batch}, len(batch), "Instagram profiles")
            if items is None:
                return None
            return {(i.get("username") or "").lower(): _slim_profile(i) for i in items if i.get("username")}

        return await self._cached_batch("ig_profile", users, PROFILE_CACHE, fetch)

    async def _reels(self, users: list[str]) -> dict[str, list[dict]]:
        async def fetch(batch: list[str]) -> Optional[dict[str, list[dict]]]:
            items = await self._run(REEL_ACTOR, {"username": batch, "resultsLimit": REELS_PER_CREATOR,
                                                 "skipPinnedPosts": True},
                                    len(batch) * REELS_PER_CREATOR + 1, "Instagram reels")
            if items is None:
                return None
            out: dict[str, list[dict]] = {u: [] for u in batch}
            for i in items:
                u = (i.get("ownerUsername") or "").lower()
                if u in out:
                    out[u].append(_slim_post(i))
            return out

        return await self._cached_batch("ig_reels", users, REEL_CACHE, fetch)

    def profile_from(self, raw: dict, reels: Optional[list[dict]] = None) -> CreatorProfile:
        bio = raw.get("biography") or ""
        links = [u["url"] for u in raw.get("externalUrls") or [] if u.get("url")]
        if raw.get("externalUrl") and raw["externalUrl"] not in links:
            links.insert(0, raw["externalUrl"])
        emails, socials, others = extract_links(" ".join([bio, *links]))
        socials.pop("instagram", None)
        username = (raw.get("username") or "").lower()
        return CreatorProfile(
            platform="instagram",
            platform_id=username,
            handle=raw.get("username") or username,
            display_name=raw.get("fullName") or raw.get("username") or username,
            bio=bio,
            url=f"https://www.instagram.com/{username}/",
            verified=bool(raw.get("verified")),
            avatar_url=raw.get("profilePicUrlHD") or raw.get("profilePicUrl"),
            followers=_int(raw.get("followersCount")) or 0,
            country=None,  # Instagram doesn't show it; Jev judges the audience country
            language=None,
            external_links=others,
            contacts={"emails": emails},
            cross_links=socials,
            recent_posts=merge_posts(raw.get("latestPosts") or [], reels or []),
            platform_stats={
                "post_count": _int(raw.get("postsCount")) or 0,
                "following": _int(raw.get("followsCount")) or 0,
                "business": bool(raw.get("isBusinessAccount")),
                "category": raw.get("businessCategoryName"),
                "private": bool(raw.get("private")),
                "instagram_id": raw.get("id"),
            },
            fetched_at=self._now(),
            source="apify:instagram",
        )

    async def fetch_profiles(self, refs: list[CandidateRef], constraints: Optional[dict] = None,
                             max_deep: Optional[int] = None) -> list[CreatorProfile]:
        """Profiles for the top candidates (one batch run, cached 7 days), the cheap filter, then view
        counts from recent reels for the best that pass (one batch run, cached 3 days)."""
        users = list(dict.fromkeys(r.platform_id.lower().lstrip("@") for r in refs if r.platform == "instagram"))
        for u in users[MAX_PROFILE_LOOKUPS:]:
            self.dropped[u] = "over the lookup limit for this run"
        users = users[:MAX_PROFILE_LOOKUPS]
        raws = await self._profiles(users)

        survivors: list[tuple[str, dict]] = []
        for u in users:
            raw = raws.get(u)
            if not raw:
                self.dropped[u] = "profile not found"
                continue
            if constraints is not None:
                ok, reason = self.cheap_filter(self.profile_from(raw), constraints)
                if not ok:
                    self.dropped[u] = reason or "filtered"
                    continue
            survivors.append((u, raw))
        budget = min(max_deep if max_deep is not None else len(survivors), MAX_REEL_CREATORS)
        for u, _ in survivors[budget:]:
            self.dropped[u] = "over the measuring limit for this run"
        survivors = survivors[:budget]

        reels = await self._reels([u for u, raw in survivors if _has_video(raw)])
        if survivors and not any(reels.values()) and any(_has_video(raw) for _, raw in survivors):
            self._warn(NO_VIEWS)
        return [self.profile_from(raw, reels.get(u)) for u, raw in survivors]

    # --- Rules and estimates ------------------------------------------------------------------------

    def cheap_filter(self, profile: CreatorProfile, constraints: dict) -> tuple[bool, Optional[str]]:
        followers = profile.get("followers") or 0
        stats = profile.get("platform_stats") or {}
        min_f, max_f = constraints.get("min_subscribers"), constraints.get("max_subscribers")
        if stats.get("private"):
            return False, "private account"
        if min_f is not None and followers < min_f:
            return False, "below the minimum follower count"
        if max_f is not None and followers > max_f:
            return False, "above the maximum follower count"
        if stats.get("post_count", 0) < MIN_POSTS:
            return False, "too few posts"
        return True, None

    def priors(self) -> PlatformPriors:
        return PlatformPriors(
            has_public_views=True,
            median_engagement_by_tier=MC.ENGAGEMENT_PRIOR["instagram"],
            ctr=MC.CTR_BY_INDUSTRY["other"],
        )

    def estimate_cost_usd(self, limits: Limits) -> float:
        searches = min(limits.max_queries, MAX_QUERIES) * RESULTS_PER_QUERY * PRICES[SEARCH_ACTOR]["result"]
        profiles = min(limits.max_candidates, MAX_PROFILE_LOOKUPS) * PRICES[PROFILE_ACTOR]["profile"]
        reels = min(limits.max_profiles, MAX_REEL_CREATORS) * REELS_PER_CREATOR * PRICES[REEL_ACTOR]["reel"]
        return math.ceil((searches + profiles + reels + PRICES[REEL_ACTOR]["actor-start"]) * 100) / 100


def _has_video(raw: dict) -> bool:
    """Only creators who post reels need the reel lookup (photos have no view counts)."""
    return any(p.get("type") == "Video" for p in raw.get("latestPosts") or [])

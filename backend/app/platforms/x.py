"""X (Twitter) on the shared pipeline (spec §6.1, roadmap F3.1), through twitterapi.io.

Cost per run with the defaults (8 searches × 2 pages, up to 150 timelines), at $0.15 per 1,000 tweets:
- search: 8 × 2 × 20 tweets ≈ 320 tweets ≈ $0.05. Each tweet carries its author's full profile, so
  profiles of found creators cost nothing extra;
- timelines: 150 × 20 tweets ≈ 3,000 tweets ≈ $0.45.
About $0.50 per full search, under the spec's $1 target.
"""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Optional

from app.metrics import constants as MC
from app.platforms.base import CandidateRef, CreatorProfile, Limits, PlatformPriors, Post, Strategy
from app.platforms.links import extract_links
from app.platforms.x_api import CREDITS_PER_TWEET, CREDITS_PER_USD, XAPI, XAPIError
from app.platforms.youtube import rank_fused

logger = logging.getLogger(__name__)

# --- Settings ---------------------------------------------------------------------------------
MIN_FAVES = 30  # a search hit needs this many likes: filters out low-reach accounts and spam
PAGES_PER_QUERY = 2  # 20 tweets a page
TWEETS_PER_PAGE = 20
TIMELINE_PAGES = 1  # 20 recent posts per creator
MIN_POSTS = 50  # accounts with fewer lifetime posts are too new or inactive
SEARCH_CACHE_HOURS = 24
FETCH_CONCURRENCY = 8
OUT_OF_CREDITS = "The X data provider is out of credits, so X results were cut short"

CacheFn = Callable[[str, Any, Optional[timedelta], Callable[[], Awaitable[Any]]], Awaitable[tuple[Any, bool]]]


async def _default_cache(namespace, key_parts, ttl, compute):
    from app.discovery.cache import cached

    return await cached(namespace, key_parts, ttl, compute)


def parse_x_time(value: Optional[str]) -> Optional[datetime]:
    """X dates look like 'Mon Nov 09 17:07:24 +0000 2026'."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%a %b %d %H:%M:%S %z %Y")
    except ValueError:
        return None


def _int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _bio(author: dict) -> str:
    return author.get("description") or (author.get("profile_bio") or {}).get("description") or ""


def _avatar(author: dict) -> Optional[str]:
    url = author.get("profilePicture")
    return url.replace("_normal.", "_400x400.") if url else None


def _media(tweet: dict) -> tuple[Optional[str], Optional[str]]:
    """(format, thumbnail) from the tweet's attached media."""
    media = ((tweet.get("extendedEntities") or {}).get("media") or [])
    if not media:
        return "text", None
    first = media[0]
    kind = first.get("type")
    fmt = "video" if kind in ("video", "animated_gif") else "image"
    return fmt, first.get("media_url_https")


def tweet_to_post(tweet: dict) -> Post:
    fmt, thumb = _media(tweet)
    shares = (_int(tweet.get("retweetCount")) or 0) + (_int(tweet.get("quoteCount")) or 0)
    return Post(
        post_id=str(tweet.get("id")),
        url=tweet.get("url") or tweet.get("twitterUrl") or "",
        text=tweet.get("text") or "",
        description="",
        published_at=parse_x_time(tweet.get("createdAt")),
        views=_int(tweet.get("viewCount")),
        likes=_int(tweet.get("likeCount")) or 0,
        comments=_int(tweet.get("replyCount")) or 0,
        shares=shares,
        is_short_form=False,
        thumbnail_url=thumb,
        format=fmt,
    )


def _own_posts(tweets: list[dict]) -> list[dict]:
    """The creator's own posts: no reposts of others, no replies."""
    return [t for t in tweets if not t.get("retweeted_tweet") and not t.get("isReply")]


class XAdapter:
    platform = "x"

    def __init__(self, api: XAPI, *, cache: Optional[CacheFn] = None, now: Optional[Callable[[], datetime]] = None):
        self.api = api
        self._cache = cache or _default_cache
        self._now = now or (lambda: datetime.now(timezone.utc))
        self.warnings: list[str] = []
        self.dropped: dict[str, str] = {}
        self._authors: dict[str, dict] = {}  # author id -> profile object seen in search results
        self._stopped = False

    def _stop(self, exc: XAPIError, what: str) -> None:
        if exc.out_of_credits:
            if not self._stopped:
                self.warnings.append(OUT_OF_CREDITS)
            self._stopped = True
        else:
            self.warnings.append(f"{what} failed: {exc.reason[:80]}")

    # --- Sourcing -------------------------------------------------------------------------------

    def _queries(self, strategy: Strategy, limits: Limits) -> list[str]:
        queries = [q.strip() for q in (strategy.queries.get("x") or strategy.topics) if q and q.strip()]
        queries = list(dict.fromkeys(queries))
        if queries and limits.query_offset:
            k = min(limits.query_offset, len(queries)) % len(queries)
            queries = queries[k:] + queries[:k]
        return queries[: max(0, limits.max_queries)]

    def _query_text(self, q: str, limits: Limits) -> str:
        text = f"{q} min_faves:{MIN_FAVES} -filter:replies -filter:retweets"
        if limits.published_within_days and not limits.order:
            since = int((self._now() - timedelta(days=max(limits.published_within_days, 30))).timestamp())
            text += f" since_time:{since}"
        return text

    async def _search(self, q: str, limits: Limits) -> list[tuple[str, str]]:
        if self._stopped:
            return []
        query = self._query_text(q, limits)

        async def run():
            tweets: list[dict] = []
            cursor = None
            for _ in range(PAGES_PER_QUERY):
                try:
                    data = await self.api.advanced_search(query, "Top", cursor)
                except XAPIError as exc:
                    if not tweets:
                        raise
                    self._stop(exc, f"search for '{q}'")  # keep the pages we already have
                    break
                tweets += data.get("tweets") or []
                cursor = data.get("next_cursor")
                if not data.get("has_next_page") or not cursor:
                    break
            # keep only what ranking and profiles need, so the cache stays small
            return [{"author": t.get("author") or {}} for t in tweets if (t.get("author") or {}).get("id")]

        key = {"platform": "x", "q": query.split(" since_time:")[0], "window": bool(" since_time:" in query)}
        try:
            hits, _ = await self._cache("search", key, timedelta(hours=SEARCH_CACHE_HOURS), run)
        except XAPIError as exc:
            self._stop(exc, f"search for '{q}'")
            return []
        out = []
        for h in hits:
            author = h["author"]
            aid = str(author["id"])
            self._authors.setdefault(aid, author)
            out.append((aid, "search"))
        return out

    async def source_candidates(self, strategy: Strategy, limits: Limits) -> list[CandidateRef]:
        queries = self._queries(strategy, limits)
        results = []
        for q in queries:  # one at a time: the provider limits requests per second anyway
            hits = await self._search(q, limits)
            # one entry per author per search, in first-seen order (several tweets by one author count once)
            results.append((q, list(dict.fromkeys(hits))))
        refs = rank_fused(results, limits.max_candidates)
        return [CandidateRef(platform="x", platform_id=r.platform_id, found_via=r.found_via, query=r.query) for r in refs]

    # --- Fetching -------------------------------------------------------------------------------

    def _author_to_profile(self, author: dict) -> CreatorProfile:
        bio = _bio(author)
        urls = [u.get("expanded_url") for u in (((author.get("entities") or {}).get("url") or {}).get("urls") or [])
                if u.get("expanded_url")]
        urls += [u.get("expanded_url") for u in (((author.get("entities") or {}).get("description") or {}).get("urls") or [])
                 if u.get("expanded_url")]
        emails, socials, others = extract_links(" ".join([bio, *urls]))
        socials.pop("x", None)
        handle = author.get("userName") or ""
        return CreatorProfile(
            platform="x",
            platform_id=str(author.get("id")),
            handle=handle,
            display_name=author.get("name") or handle,
            bio=bio,
            url=f"https://x.com/{handle}" if handle else (author.get("url") or ""),
            verified=bool(author.get("isBlueVerified") or author.get("isVerified")),
            avatar_url=_avatar(author),
            followers=_int(author.get("followers")) or 0,
            country=None,  # X shows only a free-text location; Jev judges the audience country
            language=None,
            external_links=others,
            contacts={"emails": emails},
            cross_links=socials,
            recent_posts=[],
            platform_stats={
                "post_count": _int(author.get("statusesCount")) or 0,
                "media_count": _int(author.get("mediaCount")) or 0,
                "following": _int(author.get("following")) or 0,
                "location": author.get("location") or None,
                "can_dm": bool(author.get("canDm")),
                "automated": bool(author.get("isAutomated")),
                "joined": author.get("createdAt"),
            },
            fetched_at=self._now(),
            source="twitterapi",
        )

    async def _timeline(self, user_id: str) -> list[dict]:
        if self._stopped:
            return []
        tweets: list[dict] = []
        cursor = None
        for _ in range(TIMELINE_PAGES):
            try:
                data = await self.api.last_tweets(user_id, cursor)
            except XAPIError as exc:
                self._stop(exc, f"posts for {user_id}")
                break
            body = data.get("data") if isinstance(data.get("data"), dict) else data
            tweets += body.get("tweets") or []
            cursor = data.get("next_cursor")
            if not data.get("has_next_page") or not cursor:
                break
        return tweets

    async def fetch_profiles(self, refs: list[CandidateRef], constraints: Optional[dict] = None,
                             max_deep: Optional[int] = None) -> list[CreatorProfile]:
        """Profiles from the search results (free), then the cheap filter, then each survivor's recent
        posts (20 tweets each). Creators not seen in this run's search (from our database) are looked up
        through their timeline, which carries their profile too."""
        ids = list(dict.fromkeys(r.platform_id for r in refs if r.platform == "x"))
        known = [i for i in ids if i in self._authors]
        unknown = [i for i in ids if i not in self._authors]

        survivors: list[CreatorProfile] = []
        for aid in known:
            p = self._author_to_profile(self._authors[aid])
            if constraints is not None:
                ok, reason = self.cheap_filter(p, constraints)
                if not ok:
                    self.dropped[aid] = reason or "filtered"
                    continue
            survivors.append(p)
        budget = max_deep if max_deep is not None else len(survivors) + len(unknown)
        if len(survivors) > budget:
            for p in survivors[budget:]:
                self.dropped[p["platform_id"]] = "over the measuring limit for this run"
            survivors = survivors[:budget]
        unknown = unknown[: max(0, budget - len(survivors))]

        sem = asyncio.Semaphore(FETCH_CONCURRENCY)

        async def timeline(uid: str) -> list[dict]:
            async with sem:
                return await self._timeline(uid)

        timelines = await asyncio.gather(*(timeline(p["platform_id"]) for p in survivors), *(timeline(u) for u in unknown))
        out: list[CreatorProfile] = []
        for p, tweets in zip(survivors, timelines[: len(survivors)]):
            p["recent_posts"] = self._posts(tweets)
            out.append(p)
        for uid, tweets in zip(unknown, timelines[len(survivors):]):
            author = next((t.get("author") for t in tweets if str((t.get("author") or {}).get("id")) == uid), None)
            if not author:
                self.dropped[uid] = "profile not found"
                continue
            p = self._author_to_profile(author)
            if constraints is not None:
                ok, reason = self.cheap_filter(p, constraints)
                if not ok:
                    self.dropped[uid] = reason or "filtered"
                    continue
            p["recent_posts"] = self._posts(tweets)
            out.append(p)
        return out

    @staticmethod
    def _posts(tweets: list[dict]) -> list[Post]:
        posts = [tweet_to_post(t) for t in _own_posts(tweets)]
        posts.sort(key=lambda p: p.get("published_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return posts

    # --- Rules and estimates ------------------------------------------------------------------------

    def cheap_filter(self, profile: CreatorProfile, constraints: dict) -> tuple[bool, Optional[str]]:
        followers = profile.get("followers") or 0
        stats = profile.get("platform_stats") or {}
        min_f, max_f = constraints.get("min_subscribers"), constraints.get("max_subscribers")
        if min_f is not None and followers < min_f:
            return False, "below the minimum follower count"
        if max_f is not None and followers > max_f:
            return False, "above the maximum follower count"
        if stats.get("automated"):
            return False, "automated account"
        if stats.get("post_count", 0) < MIN_POSTS:
            return False, "too few posts"
        return True, None

    def priors(self) -> PlatformPriors:
        return PlatformPriors(
            has_public_views=True,
            median_engagement_by_tier=MC.ENGAGEMENT_PRIOR["x"],
            ctr=MC.CTR_BY_INDUSTRY["other"],
        )

    def estimate_cost_usd(self, limits: Limits) -> float:
        tweets = limits.max_queries * PAGES_PER_QUERY * TWEETS_PER_PAGE + limits.max_profiles * TIMELINE_PAGES * TWEETS_PER_PAGE
        return math.ceil(tweets * CREDITS_PER_TWEET) / CREDITS_PER_USD

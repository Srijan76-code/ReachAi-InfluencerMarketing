"""LinkedIn on the shared pipeline (spec §6.3, roadmap F5.1): public, logged-out data only.

Through HarvestAPI's Apify actors, which need no LinkedIn account or cookies (spec §0: no logged-in
scraping, no fake accounts). Three batch runs per search:
1. post search for the strategy's LinkedIn searches, last month (linkedin-post-search) → people who
   wrote the most engaging posts. Company pages are dropped: we look for creators, not brands;
2. profiles for those people (linkedin-profile-scraper, no email search): followers, headline, about,
   country, websites. The cheap filter needs the follower count, which posts don't carry;
3. recent posts for the best people who pass (linkedin-profile-posts), reposts excluded.

LinkedIn shows no view counts, so metrics use reactions, comments and reposts per follower, and the
price comes from the follower tier (spec §4.5).

Cost with the defaults, at $0.002 per post and $0.004 per profile: 6 searches × 50 posts ≈ $0.60 ·
80 profiles ≈ $0.32 · 40 people × 10 posts ≈ $0.80. About $1.72 per full search (target ≤ $3).
"""

from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Optional

from app.metrics import constants as MC
from app.platforms.apify import PRICES, ApifyAPI, ApifyError, DbStore, Store
from app.platforms.base import CandidateRef, CreatorProfile, Limits, PlatformPriors, Post, Strategy
from app.platforms.links import extract_links
from app.platforms.youtube import rank_fused

logger = logging.getLogger(__name__)

# --- Settings ---------------------------------------------------------------------------------
SEARCH_ACTOR = "harvestapi/linkedin-post-search"
PROFILE_ACTOR = "harvestapi/linkedin-profile-scraper"
POSTS_ACTOR = "harvestapi/linkedin-profile-posts"

MAX_QUERIES = 6
POSTS_PER_QUERY = 50
MAX_PROFILE_LOOKUPS = 80
MAX_POST_CREATORS = 40
POSTS_PER_CREATOR = 10
MIN_FOLLOWERS = 1000  # below this a LinkedIn account is a personal network, not an audience
SEARCH_WINDOW = "month"
POSTS_WINDOW = "3months"

SEARCH_CACHE = timedelta(hours=24)
PROFILE_CACHE = timedelta(days=7)
POSTS_CACHE = timedelta(days=3)
CHARGE_MARGIN = 1.2

OUT_OF_CREDITS = "The LinkedIn data provider is out of credits, so LinkedIn results were cut short"


def parse_li_time(value: Optional[str]) -> Optional[datetime]:
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


def _engagement(item: dict) -> tuple[int, int, int]:
    e = item.get("engagement") or {}
    return max(0, _int(e.get("likes")) or 0), max(0, _int(e.get("comments")) or 0), max(0, _int(e.get("shares")) or 0)


def _slug(url_or_id: str) -> str:
    """The public identifier from a profile URL or the identifier itself ("helenchukwukelu")."""
    m = re.search(r"linkedin\.com/in/([^/?#]+)", url_or_id or "")
    return (m.group(1) if m else (url_or_id or "")).strip("/").lower()


def item_to_post(item: dict) -> Post:
    likes, comments, shares = _engagement(item)
    fmt = "article" if item.get("article") else "image" if item.get("postImages") else "text"
    images = item.get("postImages") or []
    return Post(
        post_id=str(item.get("id") or ""),
        url=item.get("linkedinUrl") or "",
        text=(item.get("content") or "")[:1000],
        description="",
        published_at=parse_li_time((item.get("postedAt") or {}).get("date")),
        views=None,  # LinkedIn doesn't show impressions publicly
        likes=likes,
        comments=comments,
        shares=shares,
        is_short_form=False,
        thumbnail_url=(images[0] or {}).get("url") if images else None,
        format=fmt,
    )


def _slim_post(item: dict) -> dict:
    author = item.get("author") or {}
    return {
        "id": item.get("id"),
        "linkedinUrl": item.get("linkedinUrl"),
        "content": (item.get("content") or "")[:1000],
        "postedAt": {"date": (item.get("postedAt") or {}).get("date")},
        "engagement": dict(zip(("likes", "comments", "shares"), _engagement(item))),
        "postImages": [{"url": i.get("url")} for i in (item.get("postImages") or [])[:1] if isinstance(i, dict)],
        "article": bool(item.get("article")),
        "author": {"publicIdentifier": author.get("publicIdentifier"), "type": author.get("type")},
    }


_PROFILE_FIELDS = ("id", "publicIdentifier", "firstName", "lastName", "headline", "followerCount", "connectionsCount",
                   "location", "websites", "about", "premium", "verified", "creator", "influencer", "openToWork",
                   "hiring", "photo", "linkedinUrl", "emails", "industry")


def _slim_profile(item: dict) -> dict:
    out = {k: item.get(k) for k in _PROFILE_FIELDS if item.get(k) is not None}
    if isinstance(out.get("about"), str):
        out["about"] = out["about"][:3000]
    pic = (item.get("profilePicture") or {}).get("url") if isinstance(item.get("profilePicture"), dict) else None
    if pic and not out.get("photo"):
        out["photo"] = pic
    return out


class LinkedInAdapter:
    platform = "linkedin"

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

    async def _run(self, actor: str, run_input: dict, planned_items: int, what: str) -> Optional[list[dict]]:
        if self._stopped or planned_items <= 0:
            return None
        price = max(PRICES.get(actor, {"x": 0.004}).values())
        cap = round(max(0.01, planned_items * price * CHARGE_MARGIN + 0.002), 4)
        try:
            return await self.api.run(actor, run_input, max_usd=cap)
        except ApifyError as exc:
            if exc.out_of_credits:
                self._stopped = True
                self._warn(OUT_OF_CREDITS)
            else:
                self._warn(f"{what} failed: {exc.reason[:80]}")
            return None

    # --- Sourcing -------------------------------------------------------------------------------

    def _queries(self, strategy: Strategy, limits: Limits) -> list[str]:
        raw = strategy.queries.get("linkedin") or strategy.topics
        queries = [re.sub(r"[#\"]", " ", q).strip() for q in raw if q and q.strip()]
        queries = list(dict.fromkeys(" ".join(q.split()) for q in queries if q))
        if queries and limits.query_offset:
            k = min(limits.query_offset, len(queries)) % len(queries)
            queries = queries[k:] + queries[:k]
        return queries[: max(0, min(limits.max_queries, MAX_QUERIES))]

    async def source_candidates(self, strategy: Strategy, limits: Limits) -> list[CandidateRef]:
        queries = self._queries(strategy, limits)
        found: dict[str, list[str]] = {}
        missing = []
        for q in queries:
            hit = await self.store.get("search", {"platform": "linkedin", "q": q.lower()})
            if hit is None:
                missing.append(q)
            else:
                found[q] = hit
        if missing:
            items = await self._run(SEARCH_ACTOR, {"searchQueries": missing, "maxPosts": POSTS_PER_QUERY,
                                                   "postedLimit": SEARCH_WINDOW, "sortBy": "relevance"},
                                    len(missing) * POSTS_PER_QUERY, "LinkedIn search")
            if items is not None:
                lower = {q.lower(): q for q in missing}
                scored: dict[str, dict[str, float]] = {q: {} for q in missing}
                for item in items:
                    author = item.get("author") or {}
                    if author.get("type") != "profile" or not author.get("publicIdentifier"):
                        continue  # company pages and showcase pages are brands, not creators
                    asked = ((item.get("query") or {}).get("search") or "").lower()
                    q = lower.get(asked) or (missing[0] if len(missing) == 1 else None)
                    if not q:
                        continue
                    likes, comments, shares = _engagement(item)
                    who = author["publicIdentifier"].lower()
                    scored[q][who] = max(scored[q].get(who, 0.0), likes + 2 * comments + 3 * shares)
                for q, people in scored.items():
                    ranked = sorted(people, key=lambda p: -people[p])  # most engaging post first
                    found[q] = ranked
                    if ranked:
                        await self.store.set("search", {"platform": "linkedin", "q": q.lower()}, ranked, SEARCH_CACHE)
        results = [(q, [(p, "search") for p in found.get(q, [])]) for q in queries]
        refs = rank_fused(results, limits.max_candidates)
        return [CandidateRef(platform="linkedin", platform_id=r.platform_id, found_via=r.found_via, query=r.query)
                for r in refs]

    # --- Fetching -------------------------------------------------------------------------------

    async def _cached_batch(self, namespace: str, ids: list[str], ttl: timedelta,
                            fetch: Callable[[list[str]], Awaitable[Optional[dict[str, Any]]]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        missing = []
        for i in ids:
            hit = await self.store.get(namespace, i)
            if hit is None:
                missing.append(i)
            else:
                out[i] = hit
        if missing:
            for i, value in (await fetch(missing) or {}).items():
                out[i] = value
                await self.store.set(namespace, i, value, ttl)
        return out

    async def _profiles(self, ids: list[str]) -> dict[str, dict]:
        async def fetch(batch: list[str]) -> Optional[dict[str, dict]]:
            items = await self._run(PROFILE_ACTOR, {"queries": [f"https://www.linkedin.com/in/{i}" for i in batch],
                                                    "profileScraperMode": "Profile details no email ($4 per 1k)"},
                                    len(batch), "LinkedIn profiles")
            if items is None:
                return None
            return {_slug(i.get("publicIdentifier") or ""): _slim_profile(i) for i in items if i.get("publicIdentifier")}

        return await self._cached_batch("li_profile", ids, PROFILE_CACHE, fetch)

    async def _posts(self, ids: list[str]) -> dict[str, list[dict]]:
        async def fetch(batch: list[str]) -> Optional[dict[str, list[dict]]]:
            items = await self._run(POSTS_ACTOR, {"targetUrls": [f"https://www.linkedin.com/in/{i}" for i in batch],
                                                  "maxPosts": POSTS_PER_CREATOR, "postedLimit": POSTS_WINDOW,
                                                  "includeReposts": False},
                                    len(batch) * POSTS_PER_CREATOR, "LinkedIn posts")
            if items is None:
                return None
            out: dict[str, list[dict]] = {i: [] for i in batch}
            for item in items:
                who = _slug((item.get("author") or {}).get("publicIdentifier") or "")
                if who in out:
                    out[who].append(_slim_post(item))
            return out

        return await self._cached_batch("li_posts", ids, POSTS_CACHE, fetch)

    def profile_from(self, raw: dict, posts: Optional[list[dict]] = None) -> CreatorProfile:
        about = raw.get("about") or ""
        headline = raw.get("headline") or ""
        sites = [s for s in raw.get("websites") or [] if isinstance(s, str)]
        emails, socials, others = extract_links(" ".join([headline, about, *sites]))
        emails = list(dict.fromkeys([*emails, *[e for e in raw.get("emails") or [] if isinstance(e, str)]]))
        socials.pop("linkedin", None)
        slug = _slug(raw.get("publicIdentifier") or "")
        name = " ".join(x for x in (raw.get("firstName"), raw.get("lastName")) if x) or slug
        location = raw.get("location") or {}
        country = (location.get("countryCode") or (location.get("parsed") or {}).get("countryCode") or None)
        recent = [item_to_post(p) for p in posts or []]
        recent.sort(key=lambda p: p.get("published_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return CreatorProfile(
            platform="linkedin",
            platform_id=slug,
            handle=slug,
            display_name=name,
            bio=headline + ("\n\n" + about if about else ""),
            url=f"https://www.linkedin.com/in/{slug}/",
            verified=bool(raw.get("verified")),
            avatar_url=raw.get("photo"),
            followers=_int(raw.get("followerCount")) or 0,
            country=country.upper() if isinstance(country, str) else None,
            language=None,
            external_links=others,
            contacts={"emails": emails},
            cross_links=socials,
            recent_posts=recent,
            platform_stats={
                "headline": headline,
                "connections": _int(raw.get("connectionsCount")) or 0,
                "creator_mode": bool(raw.get("creator")),
                "top_voice": bool(raw.get("influencer")),
                "open_to_work": bool(raw.get("openToWork")),
                "location": location.get("linkedinText"),
                "linkedin_id": raw.get("id"),
            },
            fetched_at=self._now(),
            source="apify:linkedin",
        )

    async def fetch_profiles(self, refs: list[CandidateRef], constraints: Optional[dict] = None,
                             max_deep: Optional[int] = None) -> list[CreatorProfile]:
        ids = list(dict.fromkeys(_slug(r.platform_id) for r in refs if r.platform == "linkedin" and r.platform_id))
        for i in ids[MAX_PROFILE_LOOKUPS:]:
            self.dropped[i] = "over the lookup limit for this run"
        ids = ids[:MAX_PROFILE_LOOKUPS]
        raws = await self._profiles(ids)

        survivors: list[tuple[str, dict]] = []
        for i in ids:
            raw = raws.get(i)
            if not raw:
                self.dropped[i] = "profile not found"
                continue
            if constraints is not None:
                ok, reason = self.cheap_filter(self.profile_from(raw), constraints)
                if not ok:
                    self.dropped[i] = reason or "filtered"
                    continue
            survivors.append((i, raw))
        budget = min(max_deep if max_deep is not None else len(survivors), MAX_POST_CREATORS)
        for i, _ in survivors[budget:]:
            self.dropped[i] = "over the measuring limit for this run"
        survivors = survivors[:budget]

        posts = await self._posts([i for i, _ in survivors])
        return [self.profile_from(raw, posts.get(i)) for i, raw in survivors]

    # --- Rules and estimates ------------------------------------------------------------------------

    def cheap_filter(self, profile: CreatorProfile, constraints: dict) -> tuple[bool, Optional[str]]:
        followers = profile.get("followers") or 0
        min_f = max(constraints.get("min_subscribers") or 0, MIN_FOLLOWERS)
        max_f = constraints.get("max_subscribers")
        if followers < min_f:
            return False, "below the minimum follower count"
        if max_f is not None and followers > max_f:
            return False, "above the maximum follower count"
        return True, None

    def priors(self) -> PlatformPriors:
        return PlatformPriors(
            has_public_views=False,
            median_engagement_by_tier=MC.ENGAGEMENT_PRIOR["linkedin"],
            ctr=MC.CTR_BY_INDUSTRY["other"],
        )

    def estimate_cost_usd(self, limits: Limits) -> float:
        searches = min(limits.max_queries, MAX_QUERIES) * POSTS_PER_QUERY * PRICES[SEARCH_ACTOR]["post"]
        profiles = min(limits.max_candidates, MAX_PROFILE_LOOKUPS) * PRICES[PROFILE_ACTOR]["profile"]
        posts = min(limits.max_profiles, MAX_POST_CREATORS) * POSTS_PER_CREATOR * PRICES[POSTS_ACTOR]["post"]
        return math.ceil((searches + profiles + posts) * 100) / 100

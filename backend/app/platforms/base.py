"""One creator shape for every platform, and the adapter interface (spec §4.1–4.2).

Shared pipeline steps (metrics, Jev, scoring, outreach) read only `CreatorProfile`.
Each platform (YouTube, X, Instagram, LinkedIn) implements `PlatformAdapter`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional, Protocol, TypedDict, runtime_checkable

Platform = Literal["youtube", "x", "instagram", "linkedin"]
PLATFORMS: tuple[Platform, ...] = ("youtube", "x", "instagram", "linkedin")


class Post(TypedDict, total=False):
    post_id: str
    url: str
    text: str  # YouTube: title; Instagram: caption; X/LinkedIn: post text
    description: str  # YouTube video description (not sent to Jev; used for links and sponsor checks)
    published_at: Optional[datetime]
    views: Optional[int]  # None where the platform doesn't show views (LinkedIn)
    likes: int
    comments: int
    shares: Optional[int]
    is_short_form: bool  # Shorts / Reels
    thumbnail_url: Optional[str]  # set by the adapter: video frame, image, or None for text posts
    format: Optional[str]  # set by the adapter: short | long | image | reel | carousel | text | thread


class CreatorProfile(TypedDict, total=False):
    creator_id: str  # our id; empty until saved in the creator database
    platform: Platform
    platform_id: str  # channel id / user id / username / profile slug
    handle: str
    display_name: str
    bio: str
    url: str
    verified: Optional[bool]  # None where the platform doesn't expose it (YouTube's API doesn't)
    person_id: Optional[str]  # same person across platforms (creator database)
    avatar_url: Optional[str]  # profile photo from the platform (counts as platform data: refreshed/expired like the rest)
    followers: int
    country: Optional[str]  # ISO code from the platform; None if unknown
    language: Optional[str]
    external_links: list[str]
    contacts: dict  # {"emails": [...candidates], "business_email": ..., "booking_url": ...}
    cross_links: dict  # {"instagram": url, "x": url, ...} found on the creator's own profile
    recent_posts: list[Post]  # newest first, 12–20 items
    platform_stats: dict  # extra numbers the platform gives (e.g. YouTube lifetime views, video count)
    fetched_at: datetime
    source: str  # e.g. "youtube_api", "apify:instagram-profile-scraper"


@dataclass(frozen=True)
class CandidateRef:
    """A creator found by a search, before their profile is fetched."""

    platform: Platform
    platform_id: str
    found_via: str  # "search", "trend_search", "video_search", "cross_link", "creator_db", ...
    query: Optional[str] = None


@dataclass
class Strategy:
    """Output of the strategy step, shared by all platforms."""

    topics: list[str]
    pain_points: list[str]
    queries: dict[str, list[str]]  # per platform
    trend_topics: list[str] = field(default_factory=list)
    formats: list[str] = field(default_factory=list)
    primary_metric: str = "engagement_depth"
    safety_level: Literal["low", "medium", "high", "critical"] = "medium"


@dataclass(frozen=True)
class Limits:
    max_queries: int = 8
    max_candidates: int = 300
    max_profiles: int = 150
    region: Optional[str] = None
    published_within_days: Optional[int] = 21  # for recent/trend searches
    query_offset: int = 0  # skip this many queries first (a top-up round starts with the unused ones)
    order: Optional[str] = None  # set for a top-up round: all-time post search in this order (e.g. "viewCount")


@dataclass(frozen=True)
class PlatformPriors:
    """Starting values for a platform until our own creator data replaces them."""

    has_public_views: bool
    median_engagement_by_tier: dict[str, float]  # follower tier -> typical engagement rate
    ctr: float  # share of viewers who click a link


@runtime_checkable
class PlatformAdapter(Protocol):
    platform: Platform

    async def source_candidates(self, strategy: Strategy, limits: Limits) -> list[CandidateRef]: ...

    async def fetch_profiles(
        self, refs: list[CandidateRef], constraints: Optional[dict] = None, max_deep: Optional[int] = None
    ) -> list[CreatorProfile]:
        """Fetch profiles + recent posts. With `constraints`, `cheap_filter` runs after the cheap
        profile lookup and before the expensive post fetch, so dropped creators cost nothing more.
        `max_deep` caps how many survivors get the expensive post fetch (in the order of `refs`)."""
        ...

    def cheap_filter(self, profile: CreatorProfile, constraints: dict) -> tuple[bool, Optional[str]]: ...

    def priors(self) -> PlatformPriors: ...

    def estimate_cost_usd(self, limits: Limits) -> float: ...

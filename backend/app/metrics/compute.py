"""All metrics for one creator, and the hard gates that run before any paid judging (spec §4.5)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Sequence

from app.metrics import constants as C
from app.metrics import stats
from app.metrics.anomaly import AnomalyModel, anomaly_score
from app.metrics.baselines import engagement_percentile
from app.metrics.pricing import expected_clicks, fair_range, valuation
from app.platforms.base import CreatorProfile

PLATFORMS_WITH_VIEWS = {"youtube", "x", "instagram"}


@dataclass
class BriefContext:
    """The parts of the campaign brief that metrics need."""

    industry: str = "other"
    price_tier: str = "medium"  # "low" | "medium" | "high"


@dataclass
class Metrics:
    platform: str
    followers: int
    tier: str
    has_public_views: bool
    posts_used: int
    median_views: Optional[float]
    reliability: Optional[str]
    reliability_mad: Optional[float]
    engagement_rate: Optional[float]
    engagement_percentile: Optional[float]
    comment_ratio: Optional[float]
    reach_ratio: Optional[float]  # median views per follower
    views_cv: Optional[float]
    interval_cv: Optional[float]
    days_since_last_post: Optional[int]
    posting_interval_days: Optional[float]
    momentum: Optional[float]
    outperformance: Optional[float]
    rising: bool
    anomaly_score: float
    anomaly_reasons: list[str] = field(default_factory=list)
    health: float = 0.0
    valuation: Optional[float] = None
    fair_low: Optional[float] = None
    fair_high: Optional[float] = None
    expected_clicks: Optional[int] = None

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def _round(x: Optional[float], n: int = 4) -> Optional[float]:
    return None if x is None else round(float(x), n)


def health_score(engagement_pct: Optional[float], reliability: Optional[str], days_since_last: Optional[int]) -> float:
    w = C.HEALTH_WEIGHTS
    eng = engagement_pct if engagement_pct is not None else 0.5  # unknown -> neutral, not punished
    rel = C.RELIABILITY_SCORE.get(reliability or "", 0.6)
    return round(w["engagement"] * eng + w["reliability"] * rel + w["cadence"] * stats.cadence_score(days_since_last), 4)


def compute_metrics(
    profile: CreatorProfile,
    brief: BriefContext,
    *,
    peer_engagement: Optional[Sequence[float]] = None,
    model: Optional[AnomalyModel] = None,
    now: Optional[datetime] = None,
) -> Metrics:
    platform = profile.get("platform", "youtube")
    followers = int(profile.get("followers") or 0)
    tier = stats.follower_tier(followers)
    posts = list(profile.get("recent_posts") or [])
    has_views = platform in PLATFORMS_WITH_VIEWS and any(p.get("views") is not None for p in posts)

    same_format = stats.primary_format_posts(posts) if has_views else posts
    views = stats.views_of(same_format)
    med = stats.median_views(same_format) if has_views else None
    rel_mad = stats.mad_ratio(views) if has_views else None
    rel = stats.reliability(views) if has_views else None
    er = stats.engagement_rate(same_format, followers)
    er_pct = engagement_percentile(er, platform, tier, peer_engagement)
    days = stats.days_since_last_post(posts, now)
    mom = stats.momentum(same_format) if has_views else None
    outp = stats.outperformance(same_format, followers) if has_views else None
    reach = (med / followers) if (med is not None and followers) else None

    tier_index = [name for _, name in C.FOLLOWER_TIERS].index(tier)
    rising = bool(
        (mom is not None and mom >= C.RISING_MOMENTUM and days is not None and days <= C.RISING_MAX_DAYS_SINCE_POST)
        or (outp is not None and outp >= C.RISING_OUTPERFORMANCE and tier_index <= 1)
    )

    base = {
        "followers": followers,
        "engagement_rate": er,
        "comment_ratio": stats.comment_ratio(same_format),
        "reach_ratio": reach,
        "views_cv": stats.views_cv(views),
        "interval_cv": stats.interval_cv(posts),
        "has_public_views": has_views,
    }
    a_score, a_reasons = anomaly_score(base, model)

    point = valuation(platform, med, tier, brief.industry, profile.get("country"))
    rng = fair_range(point, rel)

    return Metrics(
        platform=platform,
        followers=followers,
        tier=tier,
        has_public_views=has_views,
        posts_used=len(same_format),
        median_views=_round(med, 1),
        reliability=rel,
        reliability_mad=_round(rel_mad),
        engagement_rate=_round(er),
        engagement_percentile=_round(er_pct),
        comment_ratio=_round(base["comment_ratio"]),
        reach_ratio=_round(reach),
        views_cv=_round(base["views_cv"]),
        interval_cv=_round(base["interval_cv"]),
        days_since_last_post=days,
        posting_interval_days=_round(stats.posting_interval_days(posts), 2),
        momentum=_round(mom, 3),
        outperformance=_round(outp, 3),
        rising=rising,
        anomaly_score=a_score,
        anomaly_reasons=a_reasons,
        health=health_score(er_pct, rel, days),
        valuation=point,
        fair_low=rng[0] if rng else None,
        fair_high=rng[1] if rng else None,
        expected_clicks=expected_clicks(med, brief.industry),
    )


def view_floor(brief: BriefContext) -> float:
    floor = C.VIEW_FLOOR_BY_INDUSTRY.get(brief.industry, C.VIEW_FLOOR_BY_INDUSTRY["other"])
    return floor * C.VIEW_FLOOR_PRICE_FACTOR.get(brief.price_tier, 1.0)


def passes_gates(m: Metrics, brief: BriefContext) -> tuple[bool, Optional[str]]:
    """Hard filters. Returns (passed, reason it was dropped)."""
    if m.posts_used == 0:
        return False, "no recent posts"
    if m.days_since_last_post is not None and m.days_since_last_post > C.DEAD_AFTER_DAYS:
        return False, f"inactive for {m.days_since_last_post} days"
    if m.anomaly_score > C.ANOMALY_EXCLUDE_ABOVE:
        return False, "suspicious engagement: " + "; ".join(m.anomaly_reasons or ["unusual pattern"])
    if m.has_public_views:
        if m.median_views is None or m.median_views < C.MIN_MEDIAN_VIEWS:
            return False, "too few views"
        if m.median_views < view_floor(brief):
            return False, f"below the view floor for {brief.industry} ({brief.price_tier} price)"
    return True, None

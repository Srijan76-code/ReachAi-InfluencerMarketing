"""Robust statistics over a creator's recent posts (spec §4.5). Pure functions, no I/O."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from statistics import median
from typing import Iterable, Optional, Sequence

from app.metrics import constants as C
from app.platforms.base import Post


def follower_tier(followers: Optional[int]) -> str:
    f = followers or 0
    for upper, name in C.FOLLOWER_TIERS:
        if f < upper:
            return name
    return C.FOLLOWER_TIERS[-1][1]


def _median(values: Iterable[float]) -> Optional[float]:
    vals = [v for v in values if v is not None and not math.isnan(v)]
    return float(median(vals)) if vals else None


def primary_format_posts(posts: Sequence[Post]) -> list[Post]:
    """Long-form and short-form views differ a lot; compare like with like.
    Returns the posts of whichever format the creator posts more often (long-form on a tie)."""
    shorts = [p for p in posts if p.get("is_short_form")]
    longs = [p for p in posts if not p.get("is_short_form")]
    return shorts if len(shorts) > len(longs) else longs


def views_of(posts: Sequence[Post]) -> list[int]:
    return [int(p["views"]) for p in posts if p.get("views") is not None and p["views"] >= 0]


def median_views(posts: Sequence[Post]) -> Optional[float]:
    return _median(views_of(posts))


def mad_ratio(values: Sequence[float]) -> Optional[float]:
    """Median absolute deviation divided by the median. Robust to one viral outlier."""
    if not values:
        return None
    med = _median(values)
    if not med:
        return None
    return _median(abs(v - med) for v in values) / med


def reliability(values: Sequence[float]) -> Optional[str]:
    ratio = mad_ratio(values)
    if ratio is None:
        return None
    if ratio < C.RELIABILITY_HIGH_BELOW:
        return "High"
    if ratio < C.RELIABILITY_MEDIUM_BELOW:
        return "Medium"
    return "Low"


def engagement_rate(posts: Sequence[Post], followers: Optional[int]) -> Optional[float]:
    """Median of (likes + comments) per view; per follower where views aren't public."""
    per_post = []
    for p in posts:
        interactions = (p.get("likes") or 0) + (p.get("comments") or 0)
        views = p.get("views")
        if views is not None:
            if views > 0:
                per_post.append(interactions / views)
        elif followers:
            per_post.append(interactions / followers)
    return _median(per_post)


def comment_ratio(posts: Sequence[Post]) -> Optional[float]:
    likes = sum(p.get("likes") or 0 for p in posts)
    comments = sum(p.get("comments") or 0 for p in posts)
    return comments / likes if likes else None


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def days_since_last_post(posts: Sequence[Post], now: Optional[datetime] = None) -> Optional[int]:
    dates = [_aware(p.get("published_at")) for p in posts if p.get("published_at")]
    if not dates:
        return None
    now = _aware(now) or datetime.now(timezone.utc)
    return max(0, (now - max(dates)).days)


def posting_interval_days(posts: Sequence[Post]) -> Optional[float]:
    dates = sorted((_aware(p["published_at"]) for p in posts if p.get("published_at")), reverse=True)
    if len(dates) < 2:
        return None
    return _median((a - b).total_seconds() / 86400 for a, b in zip(dates, dates[1:]))


def interval_cv(posts: Sequence[Post]) -> Optional[float]:
    """Coefficient of variation of the gaps between posts (bursty vs steady posting)."""
    dates = sorted((_aware(p["published_at"]) for p in posts if p.get("published_at")), reverse=True)
    gaps = [(a - b).total_seconds() / 86400 for a, b in zip(dates, dates[1:])]
    if len(gaps) < 2:
        return None
    mean = sum(gaps) / len(gaps)
    if mean == 0:
        return None
    var = sum((g - mean) ** 2 for g in gaps) / len(gaps)
    return math.sqrt(var) / mean


def views_cv(values: Sequence[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    if mean == 0:
        return None
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values)) / mean


def momentum(posts_newest_first: Sequence[Post]) -> Optional[float]:
    """Median views of the newest posts divided by median views of the older ones.
    Above 1 = recent posts are doing better than before."""
    vals = views_of(posts_newest_first)
    if len(vals) < C.MIN_POSTS_FOR_MOMENTUM:
        return None
    recent = _median(vals[: C.NEWEST_N])
    older = _median(vals[C.NEWEST_N : C.COMPARE_UP_TO])
    if not older:
        return None
    return recent / older


def outperformance(posts_newest_first: Sequence[Post], followers: Optional[int]) -> Optional[float]:
    """Median views of the newest posts per follower. Above 1 = reaching beyond their followers."""
    vals = views_of(posts_newest_first)
    if not vals or not followers:
        return None
    return _median(vals[: C.NEWEST_N]) / followers


def cadence_score(days_since_last: Optional[int]) -> float:
    if days_since_last is None:
        return C.CADENCE_SCORE_FLOOR
    for limit, score in C.CADENCE_SCORE_STEPS:
        if days_since_last <= limit:
            return score
    return C.CADENCE_SCORE_FLOOR

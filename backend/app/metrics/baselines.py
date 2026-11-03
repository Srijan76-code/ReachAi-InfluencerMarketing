"""Where a creator's engagement sits compared with creators of the same platform and size
(spec §4.5). Uses real peers from the creator database once there are enough of them,
otherwise a prior median per platform and follower tier."""

from __future__ import annotations

import bisect
import math
from typing import Optional, Sequence

from app.metrics import constants as C


def percentile_among(value: float, peers: Sequence[float]) -> float:
    """Share of peers at or below `value` (0..1). `peers` need not be sorted."""
    ordered = sorted(peers)
    return bisect.bisect_right(ordered, value) / len(ordered)


def prior_percentile(value: float, prior_median: float) -> float:
    """0.5 at the prior median, 1.0 at SPREAD x the median, 0.0 at median / SPREAD (log scale)."""
    if value <= 0 or prior_median <= 0:
        return 0.0
    p = 0.5 + math.log(value / prior_median) / (2 * math.log(C.ENGAGEMENT_PRIOR_SPREAD))
    return min(1.0, max(0.0, p))


def engagement_percentile(
    engagement: Optional[float],
    platform: str,
    tier: str,
    peers: Optional[Sequence[float]] = None,
) -> Optional[float]:
    if engagement is None:
        return None
    if peers is not None and len(peers) >= C.MIN_PEERS:
        return percentile_among(engagement, peers)
    prior = C.ENGAGEMENT_PRIOR.get(platform, C.ENGAGEMENT_PRIOR["youtube"]).get(tier)
    if prior is None:
        return None
    return prior_percentile(engagement, prior)

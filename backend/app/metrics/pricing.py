"""Fair price and expected clicks for one post (spec §4.5, §8.7)."""

from __future__ import annotations

from typing import Optional

from app.metrics import constants as C


def geo_multiplier(country: Optional[str]) -> float:
    code = (country or "").upper()
    for mult, codes in C.GEO_TIERS.items():
        if code in codes:
            return mult
    return C.GEO_DEFAULT


def cpm(platform: str, industry: Optional[str], country: Optional[str]) -> float:
    base = C.INDUSTRY_CPM.get((industry or "other").lower(), C.INDUSTRY_CPM["other"])
    return round(base * geo_multiplier(country) * C.PLATFORM_CPM_FACTOR.get(platform, 1.0), 2)


def valuation(
    platform: str,
    median_views: Optional[float],
    tier: str,
    industry: Optional[str],
    country: Optional[str],
) -> Optional[float]:
    """Point estimate for one sponsored post, in USD."""
    if platform == "linkedin":
        base = C.LINKEDIN_PRICE_BY_TIER.get(tier)
        return round(base * geo_multiplier(country) / geo_multiplier("US"), 2) if base else None
    if not median_views:
        return None
    return round(median_views / 1000 * cpm(platform, industry, country), 2)


def fair_range(point: Optional[float], reliability: Optional[str]) -> Optional[tuple[float, float]]:
    if point is None:
        return None
    low, high = C.FAIR_RANGE.get(reliability or "Medium", C.FAIR_RANGE["Medium"])
    return round(point * low, 2), round(point * high, 2)


def expected_clicks(median_views: Optional[float], industry: Optional[str]) -> Optional[int]:
    if not median_views:
        return None
    return int(median_views * C.CTR_BY_INDUSTRY.get((industry or "other").lower(), C.CTR_BY_INDUSTRY["other"]))

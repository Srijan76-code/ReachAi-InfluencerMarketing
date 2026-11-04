"""Shape results like the old pipeline's `final_ranked_leads`, so the current results screen,
saved leads, outreach and export keep working. New fields are added alongside."""

from __future__ import annotations

from typing import Optional

from app.metrics.pricing import cpm


def _socials(profile: dict) -> dict:
    links = profile.get("cross_links") or {}
    emails = (profile.get("contacts") or {}).get("emails") or []
    return {
        "email": emails[0] if emails else None,  # channel description only (never video descriptions)
        "instagram": links.get("instagram"),
        "twitter": links.get("x"),
        "linkedin": links.get("linkedin"),
    }


def _iso(value) -> Optional[str]:
    return value.isoformat() if hasattr(value, "isoformat") else value


def to_legacy_lead(profile: dict, metrics: dict, record: dict, reason: Optional[str], industry: str) -> dict:
    stats = profile.get("platform_stats") or {}
    m = metrics or {}
    engagement = m.get("engagement_rate")
    clicks = m.get("expected_clicks")
    posts = profile.get("recent_posts") or []
    return {
        # --- fields the current UI reads -------------------------------------------------
        "id": profile.get("platform_id"),
        "title": profile.get("display_name") or "",
        "description": profile.get("bio") or "",
        "country": profile.get("country") or "",
        "uploads_id": stats.get("uploads_playlist"),
        "subscribers": profile.get("followers") or 0,
        "video_count": stats.get("video_count") or len(posts),
        "estimated_cpm": cpm(profile.get("platform", "youtube"), industry, profile.get("country")),
        "lifetime_health": (stats.get("lifetime_views") or 0) / max(1, stats.get("video_count") or 1),
        "metrics": {
            "avg_views": int(m.get("median_views") or 0),  # median: robust to one viral video
            "volatility": m.get("reliability_mad") or 0,
            "reliability": m.get("reliability") or "Medium",
            "engagement_rate": round((engagement or 0) * 100, 2),  # shown as %
            "raw_engagement": engagement or 0,
            "trust_score": round((m.get("engagement_percentile") or 0) * 100),
            "forecast": f"~{clicks} clicks/video" if clicks is not None else "n/a",
        },
        "socials": _socials(profile),
        "valuation": m.get("valuation") or 0,
        "recent_videos": [{"title": p.get("text", ""), "views": p.get("views") or 0, "url": p.get("url"),
                           "published_at": _iso(p.get("published_at"))} for p in posts[:8]],
        "rich_context": "",
        "semantic_score": record.get("similarity", 0),
        "relevance_score": round((record.get("fit") or 0) * 100),
        "llm_reasoning": reason or "",
        "final_score": record.get("final_score") or 0,
        "deal_status": record.get("deal_status") or "Avoid",
        "score_breakdown": {
            "strategy_score": round((record.get("fit") or 0) * 100, 1),
            "health_score": round((record.get("health") or 0) * 100),
            "risk_penalty": m.get("reliability") or "Medium",
        },
        # --- new fields --------------------------------------------------------------------
        "platform": profile.get("platform"),
        "creator_id": record.get("creator_id"),
        "url": profile.get("url"),
        "avatar_url": profile.get("avatar_url"),
        "found_via": record.get("found_via"),
        "flags": record.get("flags") or [],
        "fair_low": m.get("fair_low"),
        "fair_high": m.get("fair_high"),
        "rising": bool(m.get("rising")),
        "momentum": m.get("momentum"),
        "anomaly_score": m.get("anomaly_score"),
        "risk": record.get("risk"),
        "niche": (record.get("signals") or {}).get("niche"),
        # when the YouTube numbers were fetched; the nightly refresh updates or expires them after 30 days
        "data_as_of": _iso(profile.get("fetched_at")),
    }

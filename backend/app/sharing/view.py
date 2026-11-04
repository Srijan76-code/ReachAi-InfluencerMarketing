"""What a share link shows (spec §4.13, roadmap F1.18).

An allowlist, not a blocklist: only the fields named here leave the server, so a field added to
leads later is never shared by accident. Contact details (email, social handles) are never in it;
prices only when the owner turned them on for the link.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

ANYONE_LINK_DAYS = 30  # YouTube data may only be kept 30 days; a public link never outlives that
TOKEN_BYTES = 24  # 192-bit random token: not guessable
MAX_PEOPLE_PER_CAMPAIGN = 50
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Lead fields every link shows
LEAD_FIELDS = (
    "id", "platform", "title", "url", "avatar_url", "country", "country_source", "subscribers", "video_count",
    "final_score", "deal_status", "score_breakdown", "score_parts", "llm_reasoning", "flags", "rising", "niche",
    "verified", "trend", "data_as_of", "data_expired", "posts", "signals",
)
METRIC_FIELDS = ("avg_views", "engagement_rate", "reliability", "trust_score", "forecast", "volatility", "raw_engagement")
VIDEO_FIELDS = ("title", "views", "url", "published_at")
PRICE_FIELDS = ("valuation", "fair_low", "fair_high", "estimated_cpm")  # only with show_prices
NO_CONTACTS = {"email": None, "instagram": None, "twitter": None, "linkedin": None}


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def clean_email(value: str) -> Optional[str]:
    email = (value or "").strip().lower()
    return email if EMAIL_RE.match(email) and len(email) <= 254 else None


def anyone_link_expiry(now: Optional[datetime] = None) -> datetime:
    return (now or datetime.now(timezone.utc)) + timedelta(days=ANYONE_LINK_DAYS)


def is_live(link, now: Optional[datetime] = None) -> bool:
    now = now or datetime.now(timezone.utc)
    if link.revoked_at is not None:
        return False
    exp = link.expires_at
    if exp is not None and (exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)) <= now:
        return False
    return True


def shared_lead(lead: dict, show_prices: bool) -> dict:
    out = {k: lead.get(k) for k in LEAD_FIELDS if k in lead}
    metrics = lead.get("metrics") or {}
    out["metrics"] = {k: metrics.get(k) for k in METRIC_FIELDS if k in metrics}
    out["recent_videos"] = [{k: v.get(k) for k in VIDEO_FIELDS if k in v} for v in (lead.get("recent_videos") or [])
                            if isinstance(v, dict)]
    out["socials"] = dict(NO_CONTACTS)
    for k in PRICE_FIELDS:
        out[k] = lead.get(k) if show_prices else None
    return out


def shared_view(campaign_name: str, details: Optional[dict], leads: Optional[list], link) -> dict:
    """The JSON a share link returns."""
    wanted = set(link.creator_ids) if link.creator_ids else None
    rows = [l for l in (leads or []) if isinstance(l, dict) and (wanted is None or l.get("id") in wanted)]
    brand = ((details or {}).get("brand") or {}).get("name") or None
    return {
        "campaign_name": campaign_name,
        "shared_by": brand,
        "role": link.role,
        "show_prices": bool(link.show_prices),
        "expires_at": link.expires_at.isoformat() if link.expires_at else None,
        "creators": [shared_lead(l, bool(link.show_prices)) for l in rows],
    }

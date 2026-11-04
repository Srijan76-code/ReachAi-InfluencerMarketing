"""Fair price for a deal (spec §8.7), in code (rule 2): the fair range for this exact deal and a verdict on the
creator's quote. Negotiating itself is the agent's job (app/negotiation/)."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Optional

from app.deals import constants as C


def exclusivity_uplift(days: int) -> float:
    up = 0.0
    for from_days, value in C.EXCLUSIVITY_UPLIFT:
        if days >= from_days:
            up = value
    return up if days > 0 else 0.0


def deal_multiplier(deliverable: str, usage_rights: str, exclusivity_days: int) -> float:
    base = C.DELIVERABLE_MULTIPLIER.get(deliverable, 1.0)
    return base * (1 + C.USAGE_UPLIFT.get(usage_rights, 0.0) + exclusivity_uplift(exclusivity_days))


def _round(x: float) -> int:
    step = 1 if x < C.ROUND_SMALL_BELOW else C.ROUND_TO
    return int(step * math.ceil(x / step))


@dataclass
class Advice:
    fair_low: Optional[int]  # for this deal (format, usage, exclusivity applied)
    fair_high: Optional[int]
    verdict: Optional[str]  # great | accept | counter | walk_away | None (no quote or no fair range)
    counter: Optional[int]  # the price to offer back
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def advise(*, fair_low: Optional[float], fair_high: Optional[float], typical_views: Optional[float],
           quote: Optional[float], deliverable: str = "integration", usage_rights: str = "none",
           exclusivity_days: int = 0) -> Advice:
    if not fair_high:
        return Advice(None, None, None, None, "No fair price for this creator yet.")
    m = deal_multiplier(deliverable, usage_rights, exclusivity_days)
    low, high = _round((fair_low or fair_high * 0.75) * m), _round(fair_high * m)
    extras = " plus usage rights and exclusivity" if (usage_rights != "none" or exclusivity_days) else ""
    basis = (f"Based on about {_views(typical_views)} views per video{extras}." if typical_views
             else f"Based on the usual rate for this format{extras}.")
    if not quote:
        return Advice(low, high, None, None, basis)
    if quote <= low:
        return Advice(low, high, "great", None, f"${quote:,.0f} is below the fair range: a good price. {basis}")
    if quote <= high:
        return Advice(low, high, "accept", None, f"${quote:,.0f} is within the fair range. {basis}")
    mid = _round((low + high) / 2)
    if quote <= C.WALK_AWAY_MULTIPLE * high:
        pct = round(100 * (quote / high - 1))
        return Advice(low, high, "counter", mid, f"${quote:,.0f} is {pct}% above the top of the fair range. Counter at ${mid:,}. {basis}")
    return Advice(low, high, "walk_away", high,
                  f"${quote:,.0f} is more than {C.WALK_AWAY_MULTIPLE:g}× the fair range. Walk away, or offer ${high:,} at most. {basis}")


def _views(v: Optional[float]) -> str:
    if not v:
        return "—"
    return f"{v / 1_000_000:.1f}M" if v >= 1_000_000 else f"{v / 1000:.1f}k" if v >= 1000 else str(int(v))


DELIVERABLE_WORDS = {
    "integration": "a sponsored segment in one of your videos",
    "dedicated": "a dedicated video",
    "short": "a short",
    "post": "a post",
    "story": "a story",
}
USAGE_WORDS = {
    "none": "",
    "organic": " (including reposting it on our own channels)",
    "paid_30": " (including 30 days of use in our paid ads)",
    "paid_60": " (including 60 days of use in our paid ads)",
    "paid_90": " (including 90 days of use in our paid ads)",
}


# Words that mark a channel name rather than a person's ("The CRM Guy", "Sales Systems India").
_NOT_A_NAME = {
    "the", "a", "an", "and", "with", "of", "by", "for", "my", "our", "your", "tech", "data", "sales", "marketing", "growth",
    "money", "finance", "business", "startup", "startups", "founder", "founders", "analytics", "simplified", "systems",
    "india", "official", "channel", "tv", "media", "studio", "studios", "academy", "school", "labs", "lab", "hq", "hub",
    "daily", "weekly", "show", "podcast", "news", "world", "guy", "girl", "guru", "pro", "tips", "learn", "learning",
    "code", "coding", "dev", "ai", "crm", "saas", "notes", "talks", "life", "vlogs", "reviews", "explained", "team",
}


def greeting_name(name: Optional[str]) -> str:
    """The name to greet: a person's first name when the channel name looks like one ("Krish Naik" → Krish),
    else "there". Real first-name resolution (Jev, spec §7.1) comes with the outreach work (F6.1)."""
    words = (name or "").split()
    if 1 <= len(words) <= 3 and all(w.isalpha() and w[:1].isupper() and w[1:].islower() and w.lower() not in _NOT_A_NAME for w in words) \
            and len(words[0]) >= 2:
        return words[0]
    return "there"


def suggest_deal_type(goal: Optional[str]) -> str:
    return "base_plus_commission" if (goal or "").lower() in ("signups", "sales") else "flat"



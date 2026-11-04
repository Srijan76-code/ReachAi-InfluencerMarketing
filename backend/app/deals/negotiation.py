"""The negotiation helper (spec §8.7). Numbers only, all in code (rule 2): the fair range for this exact
deal, a verdict on the creator's quote, a counter price, and a ready-to-send message template."""

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
    return int(C.ROUND_TO * math.ceil(x / C.ROUND_TO))


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


def suggest_deal_type(goal: Optional[str]) -> str:
    return "base_plus_commission" if (goal or "").lower() in ("signups", "sales") else "flat"


def angle_for(advice: Advice, *, goal: Optional[str], signals: Optional[dict]) -> str:
    """Which way to negotiate: accept | budget | performance | scope. `signals` come from Jev reading the
    creator's own reply (app/deals/reply.py); thresholds live in app/judge/constants.py."""
    from app.judge import constants as K

    if advice.verdict in ("great", "accept"):
        return "accept"
    s = signals or {}
    if s.get("wants_commission", 0) >= K.REPLY_SIGNAL_FROM or (
            (goal or "").lower() in ("signups", "sales") and s.get("firm_price", 0) < K.REPLY_SIGNAL_FROM):
        return "performance"
    if s.get("firm_price", 0) >= K.REPLY_SIGNAL_FROM and s.get("mentions_usage", 0) >= K.REPLY_SIGNAL_FROM:
        return "scope"
    return "budget"


def amounts_for(advice: Advice, angle: str, quote: Optional[float]) -> dict:
    """The only money figures a message may contain (the LLM's output is checked against these)."""
    counter = advice.counter or advice.fair_high or 0
    if angle == "performance":
        base = _round(counter * C.BASE_SHARE_WITH_COMMISSION)
        return {"base": base, "commission_pct": C.SUGGESTED_COMMISSION_PCT, "counter": counter}
    if angle == "accept":
        return {"price": int(round(quote or advice.fair_high or 0))}
    if angle == "scope":
        return {"price": int(round(quote or 0)), "counter": counter}
    return {"counter": counter}


def template(*, name: str, advice: Advice, angle: str, amounts: dict, deliverable: str, usage_rights: str,
             post_by: Optional[str], typical_views: Optional[float]) -> str:
    first = (name or "there").split()[0]
    what = DELIVERABLE_WORDS.get(deliverable, "the collaboration")
    usage = USAGE_WORDS.get(usage_rights, "")
    when = f" going live by {post_by}" if post_by else ""
    views = f" (your recent videos get about {_views(typical_views)} views)" if typical_views else ""
    if angle == "accept":
        return (f"Hi {first},\n\nThanks for sending your rate. ${amounts['price']:,} works for us for {what}{usage}{when}. "
                f"Shall we lock in the details?\n\nThanks!")
    if angle == "performance":
        return (f"Hi {first},\n\nThanks for sending your rate. For {what}{usage}, could we do a ${amounts['base']:,} fee "
                f"plus {amounts['commission_pct']}% commission on every sale through your link? That way you earn more "
                f"the better it does.\n\nWould that work for you?")
    if angle == "scope":
        return (f"Hi {first},\n\nThanks for sending your rate. To make ${amounts['price']:,} work, could we keep it to "
                f"{what} with no paid-ads use or exclusivity? Otherwise our budget for the full package is "
                f"${amounts['counter']:,}.\n\nLet me know what you prefer.")
    return (f"Hi {first},\n\nThanks for sending your rate. Based on your typical reach{views}, our budget for {what}{usage}"
            f"{when} is ${amounts['counter']:,}.\n\nWould that work for you?")

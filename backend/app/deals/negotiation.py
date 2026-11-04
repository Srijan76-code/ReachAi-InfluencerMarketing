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


@dataclass
class History:
    """What has been offered so far (from the deal's timeline; numbers only)."""
    offers: list  # our offers, oldest first, as the full-price equivalent (a base + commission offer counts its counter)
    asks: list  # their quotes, oldest first

    @property
    def last_offer(self) -> Optional[float]:
        return self.offers[-1] if self.offers else None

    @property
    def rounds(self) -> int:
        return len(self.offers)


def next_offer(advice: Advice, quote: Optional[float], history: Optional[History]) -> tuple[Optional[int], bool]:
    """(price to offer, is it our final offer). First round: the middle of the fair range (advise). Later rounds
    move part of the way toward their ask, never below what we already offered and never above the top of the
    fair range; after MAX_ROUNDS, or at the top, it's the final offer."""
    first = advice.counter or advice.fair_high
    if not history or history.last_offer is None or not quote or not advice.fair_high:
        return first, False
    last, limit = history.last_offer, advice.fair_high
    if last >= limit:
        return int(last), True
    step = last + C.CONCESSION_SHARE * max(0.0, quote - last)
    new = max(int(last), min(limit, _round(step)))
    return new, new >= limit or history.rounds >= C.MAX_ROUNDS


def amounts_for(advice: Advice, angle: str, quote: Optional[float], counter: Optional[int] = None) -> dict:
    """The only money figures a message may contain (the LLM's output is checked against these). `counter`
    overrides the first-round counter with the history-aware one from next_offer()."""
    counter = counter or advice.counter or advice.fair_high or 0
    if angle == "performance":
        base = _round(counter * C.BASE_SHARE_WITH_COMMISSION)
        return {"base": base, "commission_pct": C.SUGGESTED_COMMISSION_PCT, "counter": counter}
    if angle == "accept":
        return {"price": int(round(quote or advice.fair_high or 0))}
    if angle == "scope":
        return {"price": int(round(quote or 0)), "counter": counter}
    return {"counter": counter}


def template(*, name: str, advice: Advice, angle: str, amounts: dict, deliverable: str, usage_rights: str,
             post_by: Optional[str], typical_views: Optional[float], again: bool = False, final: bool = False) -> str:
    """`again`: we've already made an offer (later round); `final`: this is our last offer."""
    first = greeting_name(name)
    what = DELIVERABLE_WORDS.get(deliverable, "the collaboration")
    usage = USAGE_WORDS.get(usage_rights, "")
    when = f" going live by {post_by}" if post_by else ""
    views = f" (your recent videos get about {_views(typical_views)} views)" if typical_views else ""
    if angle == "accept":
        return (f"Hi {first},\n\nThanks for sending your rate. ${amounts['price']:,} works for us for {what}{usage}{when}. "
                f"Shall we lock in the details?\n\nThanks!")
    if angle == "performance" and not again:
        return (f"Hi {first},\n\nThanks for sending your rate. For {what}{usage}, could we do a ${amounts['base']:,} fee "
                f"plus {amounts['commission_pct']}% commission on every sale through your link? That way you earn more "
                f"the better it does.\n\nWould that work for you?")
    if angle == "scope":
        return (f"Hi {first},\n\nThanks for sending your rate. To make ${amounts['price']:,} work, could we keep it to "
                f"{what} with no paid-ads use or exclusivity? Otherwise our budget for the full package is "
                f"${amounts['counter']:,}.\n\nLet me know what you prefer.")
    if again and angle in ("budget", "performance"):
        offer = (f"a ${amounts['base']:,} fee plus {amounts['commission_pct']}% commission on every sale through your link"
                 if angle == "performance" else f"${amounts['counter']:,}")
        if final:
            return (f"Hi {first},\n\nThanks for working through this with us. For {what}{usage}{when}, {offer} is the most "
                    f"we can do. If that doesn't work for you, no hard feelings, and we'd love to work together another time.")
        return (f"Hi {first},\n\nThanks for getting back to us. We can move up to {offer} for {what}{usage}{when}.\n\n"
                f"Would that work for you?")
    return (f"Hi {first},\n\nThanks for sending your rate. Based on your typical reach{views}, our budget for {what}{usage}"
            f"{when} is ${amounts['counter']:,}.\n\nWould that work for you?")

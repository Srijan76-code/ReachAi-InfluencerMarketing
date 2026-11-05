"""Everything the agent knows about a negotiation, gathered in code (free): the creator, the deal, the market,
the founder's budget and the whole conversation so far."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.deals import constants as C
from app.deals import negotiation as N
from app.negotiation import constants as NC

_MONEY = re.compile(r"(?:\$|usd\s?|rs\.?\s?|₹\s?|inr\s?)\s?(\d[\d,]*(?:\.\d+)?)\s?(k)?\b|(\d[\d,]*(?:\.\d+)?)\s?(k)?\s?(?:usd|dollars?|bucks)\b", re.I)
_BARE = re.compile(r"(?<![\d.%$])(\d[\d,]*(?:\.\d+)?)(?![\d.,]*\s?%)")
_PCT = re.compile(r"(\d{1,2}(?:\.\d+)?)\s?(?:%|percent|per cent)", re.I)


def money_candidates(text: str) -> list[int]:
    """Amounts that could be a fee: written with a currency first; if there are none, bare numbers that
    aren't percentages ("7 + 20% commission" → 7). Jev picks which one is their fee."""
    out: list[int] = []
    for m in _MONEY.finditer(text or ""):
        num, k = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        v = float(num.replace(",", "")) * (1000 if k else 1)
        if 0 < v <= C.MAX_RATE and round(v) not in out:
            out.append(int(round(v)))
    if not out:
        for m in _BARE.finditer(text or ""):
            v = float(m.group(1).replace(",", ""))
            if 0 < v <= C.MAX_RATE and round(v) not in out:
                out.append(int(round(v)))
    return out[:6]


def pct_candidates(text: str) -> list[float]:
    out: list[float] = []
    for m in _PCT.finditer(text or ""):
        v = float(m.group(1))
        if 0 < v <= 100 and v not in out:
            out.append(v)
    return out[:4]


@dataclass
class Offer:
    fee: Optional[int]
    commission_pct: float = 0

    def words(self) -> str:
        if self.fee is None and self.commission_pct:
            return f"{self.commission_pct:g}% commission only"
        fee = f"${self.fee:,}" if self.fee is not None else "no fee stated"
        return f"{fee} + {self.commission_pct:g}% commission" if self.commission_pct else fee


@dataclass
class Facts:
    """The numbers code uses to guard the agent's decision."""
    fair_low: Optional[int]
    fair_high: Optional[int]
    budget_left: Optional[float]
    our_offers: list = field(default_factory=list)  # [Offer] oldest first
    their_asks: list = field(default_factory=list)  # [Offer] oldest first

    @property
    def last_offer(self) -> Optional[Offer]:
        return self.our_offers[-1] if self.our_offers else None

    @property
    def round(self) -> int:
        return len(self.our_offers) + 1


def offer_from(payload: dict) -> Optional[Offer]:
    t = payload.get("terms") or {}
    if t:
        return Offer(t.get("fee"), float(t.get("commission_pct") or 0))
    a = payload.get("amounts") or {}  # messages sent before the agent
    if a.get("base"):
        return Offer(int(a["base"]), float(a.get("commission_pct") or 0))
    v = a.get("price") or a.get("counter")
    return Offer(int(v)) if v else None


def current_offer(d, f: Facts) -> Optional[Offer]:
    """The price on the table: what was agreed, else our last offer."""
    if d.stage in C.COMMITTED_STAGES and d.agreed_rate is not None:
        return Offer(int(round(d.agreed_rate)), float(d.commission_pct or 0) if d.deal_type != "flat" else 0.0)
    return f.last_offer


def turns(events) -> list[tuple[str, str, object]]:
    """[(who, text, event)] oldest first: our sent messages and their replies."""
    out = []
    for e in sorted(events, key=lambda e: e.created_at or 0):
        p = e.payload or {}
        if e.type == "message_sent" and p.get("text"):
            out.append(("you", p["text"], e))
        elif e.type == "creator_reply" and p.get("text"):
            out.append(("creator", p["text"], e))
    return out


def facts(d, events, *, budget_left: Optional[float]) -> Facts:
    advice = N.advise(fair_low=d.fair_low, fair_high=d.fair_high, typical_views=d.typical_views, quote=None,
                      deliverable=d.deliverable, usage_rights=d.usage_rights, exclusivity_days=d.exclusivity_days or 0)
    f = Facts(fair_low=advice.fair_low, fair_high=advice.fair_high, budget_left=budget_left)
    for e in sorted(events, key=lambda e: e.created_at or 0):
        p = e.payload or {}
        if e.type == "message_sent":
            o = offer_from(p)
            if o:
                f.our_offers.append(o)
        elif e.type == "creator_reply" and p.get("their_ask"):
            a = p["their_ask"]
            f.their_asks.append(Offer(a.get("fee"), float(a.get("commission_pct") or 0)))
    return f


def state(d, events, lead: dict, details: dict, f: Facts, reply_text: str, *, market: Optional[str],
          committed: float) -> tuple[dict, dict, dict]:
    """(Jev state, fee options, % options). Every number in `deal` is written by code."""
    lead = lead or {}
    m = lead.get("metrics") or {}
    sig = lead.get("signals") or {}
    camp = (details or {}).get("campaign") or {}
    brand = (details or {}).get("brand") or {}
    budget = camp.get("budget_total")
    convo = turns(events)[-NC.MAX_HISTORY_TURNS:]
    fees = money_candidates(reply_text)
    pcts = pct_candidates(reply_text)
    deal = {
        "creator": {
            "name": lead.get("title") or d.creator_name,
            "subscribers": lead.get("subscribers"),
            "usual_views_per_video": int(d.typical_views) if d.typical_views else None,
            "engagement_percent": m.get("engagement_rate"),
            "views_steadiness": m.get("reliability"),
            "recent_sponsored_posts": f"{sig.get('sponsored_posts', 0)} of their last {sig.get('posts_checked', 0)} posts" if sig else None,
            "recent_sponsors": sig.get("sponsor_brands") or [],
            "country": lead.get("country") or None,
        },
        "goal": camp.get("goal") or "awareness",
        "product": brand.get("name") or brand.get("product") or None,
        "deliverable": N.DELIVERABLE_WORDS.get(d.deliverable, d.deliverable),
        "usage": N.USAGE_WORDS.get(d.usage_rights, "").strip(" ()") or "their own channel only",
        "fair_price": f"${f.fair_low:,}–${f.fair_high:,}" if f.fair_high else "unknown",
        "budget": f"${budget:,.0f} total, ${max(0.0, float(budget) - committed):,.0f} not yet committed" if budget else "not set",
        "similar_deals": market,
        "round": f.round,
        "our_last_offer": f.last_offer.words() if f.last_offer else None,
        "current_price": current_offer(d, f).words() if current_offer(d, f) else None,
        "already_agreed": d.stage in C.COMMITTED_STAGES,
        "their_previous_ask": f.their_asks[-1].words() if f.their_asks else None,
    }
    history = [{"from": who, "text": text[: NC.MAX_TURN_CHARS]} for who, text, _ in convo]
    st = {"deal": deal, "history": history, "reply": {"text": (reply_text or "")[: NC.MAX_TURN_CHARS]}}
    return st, {f"f{i}": f"${v:,}" for i, v in enumerate(fees)}, {f"p{i}": f"{v:g}%" for i, v in enumerate(pcts)}

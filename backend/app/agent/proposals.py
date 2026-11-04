"""What should happen next on a deal (spec §7.8, roadmap F6.8). Pure code: looks at the deal, its timeline
and the latest pasted reply (already read by Jev) and suggests at most one or two next steps. Every
suggestion waits in the "Needs you" queue for the founder; prices come from app/deals/negotiation.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional

from app.agent import constants as A
from app.deals import constants as C
from app.deals import negotiation as N


@dataclass
class Ev:
    """One timeline entry (a DealEvent row, or a test double)."""
    id: str
    type: str
    payload: dict
    at: datetime


@dataclass
class Proposal:
    kind: str
    key: str
    title: str
    reason: str
    payload: dict = field(default_factory=dict)


_MONEY = re.compile(r"(?:\$|usd\s?)\s?(\d[\d,]*(?:\.\d+)?)\s?(k)?\b|(\d[\d,]*(?:\.\d+)?)\s?(k)?\s?(?:usd|dollars?)\b", re.I)


def money_in(text: str) -> list[int]:
    """Dollar amounts written in a message ("$1,200", "$1.2k", "800 USD"), unique, in order of appearance."""
    out: list[int] = []
    for m in _MONEY.finditer(text or ""):
        num, k = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        try:
            v = float(num.replace(",", "")) * (1000 if k else 1)
        except ValueError:
            continue
        if 0 < v <= C.MAX_RATE and int(round(v)) not in out:
            out.append(int(round(v)))
    return out


def _first(name: str) -> str:
    return N.greeting_name(name)


def follow_up_text(name: str, n: int) -> str:
    if n == 0:
        return (f"Hi {_first(name)},\n\nJust bumping this in case it got buried. We'd love to work with you on a "
                f"sponsored piece. Would you be open to it, and what's your rate?\n\nThanks!")
    return (f"Hi {_first(name)},\n\nI'll stop following up after this one. If the timing isn't right, no worries at "
            f"all; happy to circle back later. If you are interested, just reply and we'll take it from there.\n\nThanks!")


def chase_text(name: str, post_by: Optional[date], n: int) -> str:
    when = f" on {post_by.strftime('%B %-d')}" if post_by else ""
    if n == 0:
        return (f"Hi {_first(name)},\n\nQuick check on our collaboration: the post was due{when}. How is it going? "
                f"Let me know if you need anything from us, and send the link once it's live.\n\nThanks!")
    return (f"Hi {_first(name)},\n\nFollowing up on the post that was due{when}. Could you let me know when it will "
            f"go live?\n\nThanks!")


def _last(events: list[Ev], *types: str) -> Optional[Ev]:
    for e in reversed(events):
        if e.type in types:
            return e
    return None


def _offer_value(amounts: dict) -> Optional[float]:
    """An offer as one comparable number: the full price, or the counter behind a base + commission offer."""
    return amounts.get("price") or amounts.get("counter") or (amounts.get("base") / C.BASE_SHARE_WITH_COMMISSION if amounts.get("base") else None)


def history(events: list[Ev]) -> N.History:
    """Our offers (messages we sent with checked amounts) and their asks (quotes written down), oldest first."""
    offers, asks = [], []
    for e in sorted(events, key=lambda e: e.at):
        pl = e.payload or {}
        if e.type == "message_sent" and pl.get("amounts"):
            v = _offer_value(pl["amounts"])
            if v:
                offers.append(float(v))
        elif e.type == "quoted_rate" and pl.get("to"):
            asks.append(float(pl["to"]))
    return N.History(offers=offers, asks=asks)


def _offered(sent: Optional[Ev]) -> Optional[dict]:
    """The terms in the last message we sent, if it carried checked amounts."""
    if not sent:
        return None
    amounts = (sent.payload or {}).get("amounts") or {}
    if "base" in amounts:
        return {"agreed_rate": amounts["base"], "deal_type": "base_plus_commission",
                "commission_pct": amounts.get("commission_pct")}
    price = amounts.get("price") or amounts.get("counter")
    return {"agreed_rate": price} if price else None


def propose(d, events: list[Ev], *, name: str, goal: Optional[str], today: date, now: Optional[datetime] = None) -> list[Proposal]:
    """Next steps for one deal. `d` is a CreatorDeal (or anything with the same fields)."""
    from app.judge import constants as K

    now = now or datetime.now(timezone.utc)
    events = sorted(events, key=lambda e: e.at)
    F = K.REPLY_SIGNAL_FROM
    out: list[Proposal] = []
    stage = d.stage
    last_sent = _last(events, "message_sent")
    reply = _last(events, "creator_reply")
    fresh_reply = reply if reply and (not last_sent or reply.at > last_sent.at) else None
    signals = {} if not fresh_reply or (fresh_reply.payload or {}).get("signals", {}).get("ignored") else \
        (fresh_reply.payload or {}).get("signals") or {}
    rid = fresh_reply.id if fresh_reply else ""

    if stage in ("contacted", "negotiating"):
        if signals.get("declined", 0) >= F:
            return [Proposal("mark_lost", f"lost:{rid}", "Mark as lost",
                             "Their reply says they're not interested or can't do it.", {"stage": "lost"})]
        amounts = (fresh_reply.payload or {}).get("amounts") or [] if fresh_reply else []
        if signals.get("gives_price", 0) >= F:
            if len(amounts) == 1 and amounts[0] != d.quoted_rate:
                return [Proposal("record_quote", f"quote:{amounts[0]}:{rid}", f"Write down their quote: ${amounts[0]:,}",
                                 "Their reply states a price.", {"quoted_rate": amounts[0]})]
        offered = _offered(last_sent)
        if fresh_reply and offered and signals.get("agrees", 0) >= F:
            return [Proposal("agree", f"agree:{offered['agreed_rate']}:{rid}", f"Agree at ${offered['agreed_rate']:,}",
                             "Their reply accepts the offer you sent.", {**offered, "stage": "agreed"})]

        advice = N.advise(fair_low=d.fair_low, fair_high=d.fair_high, typical_views=d.typical_views, quote=d.quoted_rate,
                          deliverable=d.deliverable, usage_rights=d.usage_rights, exclusivity_days=d.exclusivity_days or 0)
        last_input = _last(events, "quoted_rate", "creator_reply")
        needs_answer = d.quoted_rate and advice.fair_high and (not last_sent or (last_input and last_input.at > last_sent.at))
        if needs_answer:
            h = history(events)
            last_sent_final = bool(last_sent and (last_sent.payload or {}).get("final"))
            if last_sent_final and advice.verdict in ("counter", "walk_away"):
                return [Proposal("mark_lost", f"lost:after-final:{int(d.quoted_rate)}:{rid}", "Mark as lost",
                                 f"They're still asking ${d.quoted_rate:,.0f} after your final offer of ${h.last_offer:,.0f}.",
                                 {"stage": "lost"})]
            angle = N.angle_for(advice, goal=goal, signals=signals)
            counter, final = N.next_offer(advice, d.quoted_rate, h) if angle != "accept" else (None, False)
            if angle != "accept" and h.last_offer and counter is not None and counter >= d.quoted_rate:
                angle = "accept"  # moving up would reach their ask: just accept it
            amts = N.amounts_for(advice, angle, d.quoted_rate, counter if angle != "accept" else None)
            again = h.rounds > 0
            text = N.template(name=name, advice=advice, angle=angle, amounts=amts, deliverable=d.deliverable,
                              usage_rights=d.usage_rights, post_by=d.post_by.strftime("%B %-d") if d.post_by else None,
                              typical_views=d.typical_views, again=again, final=final)
            key = f"{angle}:{int(d.quoted_rate)}:{sorted(amts.items())}:{d.deliverable}:{d.usage_rights}:{d.exclusivity_days or 0}:{h.rounds}:{rid}"
            if angle == "accept":
                return [Proposal("agree", f"agree:{key}", f"Accept ${amts['price']:,} and agree",
                                 advice.reason if not again else f"${amts['price']:,} is within your limit.",
                                 {"agreed_rate": amts["price"], "stage": "agreed", "message": text,
                                  "angle": angle, "amounts": amts})]
            offer = (f"${amts.get('base', 0):,} + {amts.get('commission_pct')}% commission" if angle == "performance"
                     else f"${amts.get('price', 0):,} with a smaller scope" if angle == "scope" else f"${amts.get('counter', 0):,}")
            title = f"Final offer: {offer}" if final else (f"Offer {offer}" if again else
                    {"performance": f"Offer {offer}", "scope": f"Keep {offer}", "budget": f"Counter at {offer}"}[angle])
            if again:
                reason = (f"Round {h.rounds + 1}. You offered ${h.last_offer:,.0f}, they ask ${d.quoted_rate:,.0f}. "
                          + ("This is the top of the fair range." if final and counter >= (advice.fair_high or 0)
                             else "Last round before a final offer." if h.rounds + 1 >= C.MAX_ROUNDS
                             else f"Moves part of the way toward their ask, within the fair range (up to ${advice.fair_high:,})."))
            else:
                reason = advice.reason
            return [Proposal("send_counter", f"counter:{key}", title, reason,
                             {"message": text, "angle": angle, "amounts": amts, "final": final, "round": h.rounds + 1})]

        if not fresh_reply and not d.quoted_rate:
            since = last_sent.at if last_sent else getattr(d, "created_at", None)
            n = sum(1 for e in events if e.type == "message_sent" and (e.payload or {}).get("kind") == "follow_up")
            if since and n < A.MAX_FOLLOW_UPS and (now - since).days >= A.FOLLOW_UP_AFTER_DAYS:
                out.append(Proposal("follow_up", f"follow_up:{n}", "Send a follow-up" if n == 0 else "Send a last follow-up",
                                    f"No answer for {(now - since).days} days.", {"message": follow_up_text(name, n)}))
        return out

    if stage in C.POST_DUE_STAGES:
        if d.post_url:
            return [Proposal("mark_live", f"live:{d.post_url}", "Move to Live", "The post link is in.", {"stage": "live"})]
        if d.post_by and d.post_by < today:
            chases = [e for e in events if e.type == "message_sent" and (e.payload or {}).get("kind") == "chase_post"]
            if len(chases) < A.MAX_CHASES and (not chases or (now - chases[-1].at).days >= A.CHASE_AGAIN_AFTER_DAYS):
                late = (today - d.post_by).days
                out.append(Proposal("chase_post", f"chase:{d.post_by.isoformat()}:{len(chases)}", "Ask about the late post",
                                    f"The post was due {late} day{'s' if late != 1 else ''} ago and there's no link yet.",
                                    {"message": chase_text(name, d.post_by, len(chases))}))
        return out

    if stage == "live" and d.agreed_rate and not d.paid_at:
        return [Proposal("mark_paid", f"paid:{int(d.agreed_rate)}", f"Mark paid (${d.agreed_rate:,.0f})",
                         "The post is live. Pay them, then mark it paid here. ReachAI doesn't move money.",
                         {"stage": "paid"})]
    return out

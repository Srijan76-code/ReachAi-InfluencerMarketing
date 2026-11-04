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


def propose(d, events: list[Ev], *, name: str, goal: Optional[str], today: date, now: Optional[datetime] = None) -> list[Proposal]:
    """Next steps for one deal. `d` is a CreatorDeal (or anything with the same fields)."""
    now = now or datetime.now(timezone.utc)
    events = sorted(events, key=lambda e: e.at)
    out: list[Proposal] = []
    stage = d.stage
    last_sent = _last(events, "message_sent")
    reply = _last(events, "creator_reply")
    fresh_reply = reply if reply and (not last_sent or reply.at > last_sent.at) else None

    # replies, prices, counters and agreeing are the negotiation agent's job (app/negotiation/), run when a
    # reply arrives; here only the time-based nudges
    if stage in ("contacted", "negotiating"):
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

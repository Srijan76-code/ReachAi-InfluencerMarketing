"""Agreeing a deal (spec §7.8, roadmap F7.10c): the posts the creator will make (each with a date), when they're
paid, and their tracking link and discount code, then a confirmation message written by code (rule 2: every
number and date here comes from code, nothing from a model)."""

from __future__ import annotations

import re
import secrets
import string
from datetime import date
from typing import Optional
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deals import constants as C
from app.deals import negotiation as N
from app.models.deal import CreatorDeal, DealPost, TrackingLink

_SLUG_ALPHABET = string.ascii_lowercase + string.digits
DELIVERABLE_PLURAL = {"integration": "sponsored segments", "dedicated": "dedicated videos", "short": "shorts", "post": "posts", "story": "stories"}
DELIVERABLE_ONE = {"integration": "sponsored segment", "dedicated": "dedicated video", "short": "short", "post": "post", "story": "story"}


def clean_url(url: Optional[str]) -> Optional[str]:
    """The founder's site for the tracking link: https only (http is upgraded), a real host, no tricks."""
    u = (url or "").strip()
    if not u:
        return None
    if not re.match(r"^https?://", u, re.I):
        u = "https://" + u
    p = urlparse(u)
    if p.scheme not in ("http", "https") or not p.hostname or "." not in p.hostname or len(u) > 500:
        raise HTTPException(422, "That doesn't look like a web address.")
    return u.replace("http://", "https://", 1) if p.scheme == "http" else u


def code_for(name: str, taken: set[str]) -> str:
    """A discount code from their name, like SRIJAN10, unique in the campaign."""
    base = re.sub(r"[^A-Z]", "", (N.greeting_name(name) if N.greeting_name(name) != "there" else name).upper())[:8] or "CREATOR"
    for _ in range(50):
        code = base + "".join(secrets.choice(string.digits) for _ in range(C.TRACKING_CODE_DIGITS))
        if code not in taken:
            return code
    return base + secrets.token_hex(2).upper()


def new_slug() -> str:
    return "".join(secrets.choice(_SLUG_ALPHABET) for _ in range(C.TRACKING_SLUG_CHARS))


def _day(d: date) -> str:
    return d.strftime("%b %-d")


def posts_words(posts: list[tuple[str, Optional[date]]]) -> list[str]:
    """["1 sponsored segment by Nov 20", "2 shorts by Nov 25"]: same kind and date grouped."""
    groups: dict[tuple[str, Optional[date]], int] = {}
    for kind, due in posts:
        groups[(kind, due)] = groups.get((kind, due), 0) + 1
    out = []
    for (kind, due), n in groups.items():
        what = f"1 {DELIVERABLE_ONE.get(kind, kind)}" if n == 1 else f"{n} {DELIVERABLE_PLURAL.get(kind, kind)}"
        out.append(what + (f" by {_day(due)}" if due else ""))
    return out


def confirmation(name: str, price: str, posts: list[tuple[str, Optional[date]]], pay_when: Optional[str],
                 link: Optional[str], code: Optional[str]) -> str:
    hi = f"Hi {name},\n\n" if name and name != "there" else "Hi there,\n\n"
    lines = [f"- {w}" for w in posts_words(posts)]
    lines.append(f"- {price}" + (f", paid {C.PAY_WHEN[pay_when]}" if pay_when in C.PAY_WHEN else ""))
    body = hi + "Great, we're all set! Here's what we agreed:\n" + "\n".join(lines)
    if link or code:
        body += "\n\nSo we can see how it does, please use"
        body += f" this link: {link}" if link else ""
        body += (" and" if link else "") + (f" this code for your audience: {code}" if code else "")
        body += "."
    body += "\n\nSend over the link once it's live. Thanks, excited to work together!"
    return body


async def save_posts(db: AsyncSession, d: CreatorDeal, posts: list[dict]) -> list[tuple[str, Optional[date]]]:
    """Replaces the deal's planned posts (keeps ones already live). → [(deliverable, due_on)]"""
    if not posts:
        raise HTTPException(422, "Add at least one post.")
    if len(posts) > C.MAX_POSTS:
        raise HTTPException(422, f"Up to {C.MAX_POSTS} posts per deal.")
    for p in posts:
        if p.get("deliverable") not in C.DELIVERABLE_MULTIPLIER:
            raise HTTPException(422, "Unknown kind of post.")
    await db.execute(delete(DealPost).where(DealPost.deal_id == d.deal_id, DealPost.post_url.is_(None)))
    out = []
    for i, p in enumerate(posts):
        db.add(DealPost(deal_id=d.deal_id, deliverable=p["deliverable"], due_on=p.get("due_on"), position=i))
        out.append((p["deliverable"], p.get("due_on")))
    dues = [due for _, due in out if due]
    d.post_by = min(dues) if dues else None
    d.deliverable = out[0][0]
    return out


async def ensure_tracking(db: AsyncSession, d: CreatorDeal, name: str, target: Optional[str]) -> tuple[Optional[TrackingLink], str]:
    """The creator's link (when there's a site to send people to) and code; made once, the target can change."""
    link = (await db.execute(select(TrackingLink).where(TrackingLink.deal_id == d.deal_id))).scalars().first()
    if target:
        if link is None:
            link = TrackingLink(slug=new_slug(), deal_id=d.deal_id, campaign_id=d.campaign_id, target_url=target)
            db.add(link)
        else:
            link.target_url = target
    if not d.tracking_code:
        taken = set((await db.execute(select(CreatorDeal.tracking_code).where(
            CreatorDeal.campaign_id == d.campaign_id, CreatorDeal.tracking_code.is_not(None)))).scalars())
        d.tracking_code = code_for(name, taken)
    return link, d.tracking_code

"""Changing a deal (spec §8.1): the same checks and timeline entries whether the founder edits the deal or
approves a suggestion from the "Needs you" queue."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.deals import constants as C
from app.models.deal import CreatorDeal, DealEvent

PLATFORM_HOSTS = {"youtube": ("youtube.com", "youtu.be"), "instagram": ("instagram.com",), "x": ("x.com", "twitter.com"),
                  "linkedin": ("linkedin.com",)}
EDITABLE = ("stage", "deliverable", "post_by", "deal_type", "commission_pct", "usage_rights", "exclusivity_days",
            "disclosure", "quoted_rate", "agreed_rate", "post_url", "paid_amount", "paid_at", "payment_ref", "notes", "position",
            "contact_email", "fair_low", "fair_high")


_EMAIL = re.compile(r"[^@\s<>]+@[^@\s<>]+\.[a-z]{2,}")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def validate(d: CreatorDeal, ch: dict) -> None:
    def bad(msg: str):
        raise HTTPException(422, msg)

    if "stage" in ch and ch["stage"] not in C.STAGES:
        bad("Unknown stage.")
    if "deliverable" in ch and ch["deliverable"] not in C.DELIVERABLE_MULTIPLIER:
        bad("Unknown deliverable.")
    if "deal_type" in ch and ch["deal_type"] not in C.DEAL_TYPES:
        bad("Unknown deal type.")
    if "usage_rights" in ch and ch["usage_rights"] not in C.USAGE_UPLIFT:
        bad("Unknown usage rights.")
    for k in ("quoted_rate", "agreed_rate", "paid_amount"):
        if ch.get(k) is not None and not (0 <= ch[k] <= C.MAX_RATE):
            bad("Prices must be between $0 and $10M.")
    if ch.get("commission_pct") is not None and not (0 <= ch["commission_pct"] <= 100):
        bad("Commission must be 0–100%.")
    if ch.get("exclusivity_days") is not None and not (0 <= ch["exclusivity_days"] <= 365):
        bad("Exclusivity must be 0–365 days.")
    if ch.get("notes") and len(ch["notes"]) > C.MAX_NOTES_CHARS:
        bad("Notes are too long.")
    for k in ("fair_low", "fair_high"):
        if ch.get(k) is not None and not (0 < ch[k] <= C.MAX_RATE):
            bad("Fair prices must be between $1 and $10M.")
    low, high = ch.get("fair_low", d.fair_low), ch.get("fair_high", d.fair_high)
    if low is not None and high is not None and low > high:
        bad("The low end of the fair price can't be above the high end.")
    if "contact_email" in ch:
        e = (ch["contact_email"] or "").strip().lower() or None
        if e and not _EMAIL.fullmatch(e):
            bad("That doesn't look like an email address.")
        ch["contact_email"] = e
    if ch.get("post_url"):
        u = urlparse(ch["post_url"].strip())
        hosts = PLATFORM_HOSTS.get(d.platform, ())
        host = (u.hostname or "").lower()
        if u.scheme not in ("http", "https") or (hosts and not any(host == h or host.endswith("." + h) for h in hosts)):
            bad(f"That doesn't look like a {d.platform.title()} link.")



def apply_change(db: AsyncSession, d: CreatorDeal, ch: dict) -> None:
    """Checks and applies a change, and adds its timeline entries (the caller commits)."""
    validate(d, ch)
    events = []
    if "stage" in ch and ch["stage"] != d.stage:
        events.append(("stage", {"from": d.stage, "to": ch["stage"]}))
        if ch["stage"] == "live" and not d.live_at:
            d.live_at = _now()
        if ch["stage"] == "paid" and not d.paid_at and "paid_at" not in ch:
            d.paid_at = _now()
            if d.paid_amount is None and "paid_amount" not in ch:
                d.paid_amount = d.agreed_rate
    for k in ("quoted_rate", "agreed_rate"):
        if k in ch and ch[k] != getattr(d, k):
            events.append((k, {"from": getattr(d, k), "to": ch[k]}))
    if ch.get("post_url") and ch["post_url"] != d.post_url:
        events.append(("post_url", {"to": ch["post_url"].strip()}))
        ch["post_url"] = ch["post_url"].strip()
    if "paid_at" in ch and ch["paid_at"] and not d.paid_at:
        events.append(("paid", {"amount": ch.get("paid_amount", d.paid_amount or d.agreed_rate)}))
    for k in EDITABLE:
        if k in ch:
            setattr(d, k, ch[k])
    d.updated_at = _now()
    for t, payload in events:
        db.add(DealEvent(deal_id=d.deal_id, type=t, payload=payload))

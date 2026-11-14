"""The contact ledger and the global suppression list (spec §7.1 steps 7–8). Only hashes of addresses are kept."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contacts import constants as C
from app.models.contact import ContactHistory, Suppression


def address_hash(address: str) -> str:
    return hashlib.sha256((address or "").strip().lower().encode()).hexdigest()


async def suppressed(db: AsyncSession, address: Optional[str]) -> Optional[str]:
    """The reason an address must not be emailed (opt_out, bounce, complaint), or None."""
    if not address:
        return None
    row = await db.get(Suppression, address_hash(address))
    return row.reason if row else None


async def suppress(db: AsyncSession, address: str, reason: str) -> None:
    h = address_hash(address)
    if await db.get(Suppression, h) is None:
        db.add(Suppression(address_hash=h, reason=reason))


async def record_contact(db: AsyncSession, user_id: str, address: str, campaign_id: Optional[str],
                         outcome: str = "sent", channel: str = "email") -> None:
    h = address_hash(address)
    now = datetime.now(timezone.utc)
    row = (await db.execute(select(ContactHistory).where(ContactHistory.user_id == user_id,
                                                         ContactHistory.address_hash == h))).scalar_one_or_none()
    if row is None:
        db.add(ContactHistory(user_id=user_id, address_hash=h, channel=channel, campaign_id=campaign_id,
                              first_contacted_at=now, last_contacted_at=now, last_outcome=outcome))
    else:
        row.last_contacted_at, row.last_outcome = now, outcome
        row.campaign_id = campaign_id or row.campaign_id


async def contacted_recently(db: AsyncSession, user_id: str, addresses: list[str],
                             not_campaign: Optional[str] = None) -> dict[str, datetime]:
    """{address: last contacted} for addresses this founder contacted in the last 90 days, in another campaign."""
    wanted = {address_hash(a): a for a in addresses if a}
    if not wanted:
        return {}
    since = datetime.now(timezone.utc) - timedelta(days=C.RECENTLY_CONTACTED_DAYS)
    rows = (await db.execute(select(ContactHistory).where(ContactHistory.user_id == user_id,
                                                          ContactHistory.address_hash.in_(list(wanted))))).scalars().all()
    out = {}
    for r in rows:
        at = r.last_contacted_at
        if at and at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        if at and at >= since and (not_campaign is None or r.campaign_id != not_campaign):
            out[wanted[r.address_hash]] = at
    return out

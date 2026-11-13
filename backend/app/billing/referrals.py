"""Invites: a founder shares a link; when the new user's first search completes, both get credits (spec §5.2).

Limits against abuse: only accounts created in the last `REFERRAL_CLAIM_WINDOW` can claim, one claim per
account, never your own code, credits only after a real search finishes (credits spent, enough creators
found), and at most `REFERRALS_PER_YEAR` grants per referrer.
"""

from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import constants as C
from app.billing import ledger
from app.models.billing import Referral, ReferralCode
from app.models.user import User

ALPHABET = string.ascii_lowercase + string.digits


class ReferralError(Exception):
    """Why an invite can't be used, in words a user can read."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def code_for(db: AsyncSession, user_id: str) -> str:
    row = await db.get(ReferralCode, user_id)
    if row:
        return row.code
    for _ in range(5):
        code = "".join(secrets.choice(ALPHABET) for _ in range(C.REFERRAL_CODE_LENGTH))
        try:
            async with db.begin_nested():
                db.add(ReferralCode(user_id=user_id, code=code))
            return code
        except IntegrityError:
            continue
    raise RuntimeError("could not make a unique referral code")


async def claim(db: AsyncSession, user: User, code: str, now: datetime | None = None) -> str:
    """Record that `user` came from `code`. Returns the referrer's user id. Raises ReferralError."""
    now = now or _now()
    code = (code or "").strip().lower()
    owner = await db.scalar(select(ReferralCode.user_id).where(ReferralCode.code == code))
    if not owner:
        raise ReferralError("That invite link isn't valid.")
    if owner == user.user_id:
        raise ReferralError("You can't use your own invite.")
    if await db.get(Referral, user.user_id):
        raise ReferralError("You've already used an invite.")
    created = ledger.aware(user.created_at) if user.created_at else now
    if now - created > C.REFERRAL_CLAIM_WINDOW:
        raise ReferralError("Invites are for new accounts.")
    db.add(Referral(referred_user_id=user.user_id, referrer_user_id=owner))
    await db.flush()
    return owner


async def grant_after_first_search(db: AsyncSession, user_id: str, now: datetime | None = None) -> bool:
    """Called when one of `user_id`'s searches is committed. Grants both sides once. Returns True if granted."""
    now = now or _now()
    ref = await db.get(Referral, user_id)
    if ref is None or ref.granted_at is not None:
        return False
    ref.granted_at = now  # mark first, so a retried settle can't grant twice
    year_ago = now - timedelta(days=365)
    earned = await db.scalar(
        select(func.count()).select_from(Referral)
        .where(Referral.referrer_user_id == ref.referrer_user_id, Referral.granted_at.is_not(None),
               Referral.granted_at >= year_ago, Referral.referred_user_id != user_id)
    )
    await ledger.grant_referral(db, user_id, C.REFERRAL_CREDITS, user_id, "Joined through an invite")
    if (earned or 0) < C.REFERRALS_PER_YEAR:
        await ledger.grant_referral(db, ref.referrer_user_id, C.REFERRAL_CREDITS, user_id, "A founder you invited ran a search")
    await db.flush()
    return True


async def summary(db: AsyncSession, user_id: str) -> dict:
    code = await code_for(db, user_id)
    invited = await db.scalar(select(func.count()).select_from(Referral).where(Referral.referrer_user_id == user_id))
    rewarded = await db.scalar(select(func.count()).select_from(Referral)
                               .where(Referral.referrer_user_id == user_id, Referral.granted_at.is_not(None)))
    return {"code": code, "invited": int(invited or 0), "rewarded": int(rewarded or 0),
            "credits_each": C.REFERRAL_CREDITS}

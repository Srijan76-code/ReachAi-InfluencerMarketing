"""Credits: balances, monthly grants, and reserve → commit / release for each search (spec §5.3).

Every change is a `credit_ledger` row; a balance is the sum of rows per bucket. All writes for one user
run under a per-user lock (Postgres advisory lock), so two searches started at once can never spend the
same credit. Functions here never commit: the caller commits, so a reservation and the campaign update
it belongs to land together.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import constants as C
from app.models.billing import CreditEntry, CreditReservation, Subscription


class NotEnoughCredits(Exception):
    def __init__(self, needed: int, balance: int):
        self.needed, self.balance = needed, balance
        super().__init__(f"This search needs {needed} credit{'s' if needed != 1 else ''}; you have {balance}.")


class DailyLimitReached(Exception):
    pass


@dataclass(frozen=True)
class Quote:
    credits: int
    platforms: list[str]
    find_more: bool


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:  # SQLite hands back naive datetimes
        return dt.replace(tzinfo=timezone.utc)
    return dt


aware = _aware


def month_bounds(now: datetime) -> tuple[datetime, datetime]:
    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    end = datetime(now.year + (now.month == 12), now.month % 12 + 1, 1, tzinfo=timezone.utc)
    return start, end


async def lock(db: AsyncSession, user_id: str) -> None:
    if db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"credits:{user_id}"})


def quote(details: dict | None, *, find_more: bool = False) -> Quote:
    """What a search with this brief costs. Only live platforms are charged."""
    chosen = [str(p).lower() for p in ((details or {}).get("campaign") or {}).get("platforms") or []]
    platforms = [p for p in C.LIVE_PLATFORMS if not chosen or p in chosen] or list(C.LIVE_PLATFORMS)
    full = sum(C.SEARCH_CREDITS[p] for p in platforms)
    credits = math.ceil(full * C.FIND_MORE_FACTOR) if find_more else full
    return Quote(credits=max(1, credits), platforms=platforms, find_more=find_more)


def _entry(user_id: str, delta: int, bucket: str, reason: str, ref_type: str | None, ref_id: str | None,
           note: str | None = None) -> CreditEntry:
    return CreditEntry(user_id=user_id, delta=delta, bucket=bucket, reason=reason, ref_type=ref_type,
                       ref_id=ref_id, note=note)


async def balances(db: AsyncSession, user_id: str) -> dict[str, int]:
    rows = await db.execute(
        select(CreditEntry.bucket, func.coalesce(func.sum(CreditEntry.delta), 0))
        .where(CreditEntry.user_id == user_id).group_by(CreditEntry.bucket)
    )
    found = {bucket: int(total) for bucket, total in rows.all()}
    return {b: max(0, found.get(b, 0)) for b in C.BUCKETS}


async def _close_period(db: AsyncSession, sub: Subscription, next_start: datetime, carry: bool) -> None:
    """Expire what's left of the current period; with `carry`, move unused monthly credits (up to one
    month's worth) into rollover for the next period. Old rollover always expires."""
    plan = C.PLANS.get(sub.plan, C.PLANS[C.DEFAULT_PLAN])
    old_ref = _aware(sub.current_period_start).isoformat()
    left = await balances(db, sub.user_id)
    if left["rollover"]:
        db.add(_entry(sub.user_id, -left["rollover"], "rollover", "expire", "period", old_ref))
    if left["monthly"]:
        db.add(_entry(sub.user_id, -left["monthly"], "monthly", "expire", "period", old_ref))
    if carry and plan["rollover"] and left["monthly"]:
        carried = min(left["monthly"], plan["monthly"])
        db.add(_entry(sub.user_id, carried, "rollover", "rollover", "period", next_start.isoformat(),
                      "Unused credits from last month"))


def _grant_month(db: AsyncSession, sub: Subscription, ref: str) -> None:
    plan = C.PLANS.get(sub.plan, C.PLANS[C.DEFAULT_PLAN])
    db.add(_entry(sub.user_id, plan["monthly"], "monthly", "grant_plan", "period", ref))


def _lapsed(sub: Subscription, now: datetime) -> bool:
    """A paid plan whose period ended without a renewal (cancelled, or unpaid past the grace period)."""
    end = _aware(sub.current_period_end)
    if sub.status == "cancelled":
        return now >= end
    return now >= end + C.RENEWAL_GRACE


async def ensure_account(db: AsyncSession, user_id: str, now: datetime | None = None) -> Subscription:
    """Create the Free plan with welcome credits on first use, and start a new period when one has ended.

    Free periods are calendar months, granted here. Paid periods follow the payment provider and are granted
    by its renewal webhook (`start_paid_period`); a paid plan that lapses falls back to Free here.
    Safe to call on every read; grants are written once per period (unique ledger refs). Takes the lock.
    """
    now = now or _now()
    await lock(db, user_id)
    sub = await db.get(Subscription, user_id)
    if sub is None:
        start, end = month_bounds(now)
        sub = Subscription(user_id=user_id, plan=C.DEFAULT_PLAN, current_period_start=start, current_period_end=end)
        db.add(sub)
        db.add(_entry(user_id, C.WELCOME_CREDITS, "bonus", "grant_welcome", "welcome", user_id, "Welcome credits"))
        _grant_month(db, sub, start.isoformat())
        await db.flush()
        return sub

    if now < _aware(sub.current_period_end):
        return sub
    if sub.plan != C.DEFAULT_PLAN:
        if not _lapsed(sub, now):
            return sub  # waiting for the renewal webhook
        start, end = month_bounds(now)
        await _close_period(db, sub, start, carry=False)
        sub.plan, sub.status, sub.cancel_at_period_end = C.DEFAULT_PLAN, "cancelled", False
    else:
        start, end = month_bounds(now)
        await _close_period(db, sub, start, carry=False)  # Free never rolls over
    sub.current_period_start, sub.current_period_end = start, end
    _grant_month(db, sub, start.isoformat())
    await db.flush()
    return sub


async def start_paid_period(db: AsyncSession, user_id: str, plan: str, start: datetime, end: datetime,
                            *, provider_subscription_id: str, provider_customer_id: str | None) -> bool:
    """A paid plan started or renewed (webhook). Closes the old period and grants the plan's monthly credits.

    Idempotent and order-safe: a repeat of the same period, or an older one arriving late, changes only the
    end date. Returns True if credits were granted.
    """
    sub = await ensure_account(db, user_id, start)
    sub.provider = "dodo"
    sub.provider_subscription_id = provider_subscription_id
    if provider_customer_id:
        sub.provider_customer_id = provider_customer_id
    sub.status = "active"
    current_start = _aware(sub.current_period_start)
    if sub.plan == plan and start <= current_start + C.PERIOD_MATCH:
        if start >= current_start - C.PERIOD_MATCH:  # the same period again: keep the latest end date
            sub.current_period_end = max(_aware(sub.current_period_end), end)
        await db.flush()
        return False
    # Renewing straight into the next period (same or another paid plan) rolls unused credits over.
    consecutive = sub.plan != C.DEFAULT_PLAN and abs(start - _aware(sub.current_period_end)) <= C.PERIOD_MATCH
    await _close_period(db, sub, start, carry=consecutive)
    sub.plan, sub.current_period_start, sub.current_period_end = plan, start, end
    sub.cancel_at_period_end = False
    _grant_month(db, sub, f"{provider_subscription_id}:{start.isoformat()}")
    await db.flush()
    return True


async def change_plan(db: AsyncSession, user_id: str, plan: str, ref: str) -> int:
    """The plan changed inside a paid period (webhook). An upgrade adds the difference in monthly credits now;
    a downgrade takes effect from the next period. Returns the credits added."""
    sub = await ensure_account(db, user_id)
    old = C.PLANS.get(sub.plan, C.PLANS[C.DEFAULT_PLAN])["monthly"]
    new = C.PLANS[plan]["monthly"]
    sub.plan = plan
    added = 0
    if new > old:
        exists = await db.scalar(select(func.count()).select_from(CreditEntry).where(
            CreditEntry.user_id == user_id, CreditEntry.reason == "grant_plan", CreditEntry.ref_id == ref))
        if not exists:
            added = new - old
            db.add(_entry(user_id, added, "monthly", "grant_plan", "plan_change", ref, f"Upgraded to {plan.title()}"))
    await db.flush()
    return added


async def set_status(db: AsyncSession, user_id: str, status: str, cancel_at_period_end: bool | None = None) -> None:
    sub = await ensure_account(db, user_id)
    if sub.plan == C.DEFAULT_PLAN and status != "active":
        return
    sub.status = status
    if cancel_at_period_end is not None:
        sub.cancel_at_period_end = cancel_at_period_end
    await db.flush()


async def grant_pack(db: AsyncSession, user_id: str, credits: int, payment_id: str, note: str) -> bool:
    """Credits bought as a pack (never expire). Once per payment."""
    await ensure_account(db, user_id)
    exists = await db.scalar(select(func.count()).select_from(CreditEntry).where(
        CreditEntry.user_id == user_id, CreditEntry.reason == "grant_pack", CreditEntry.ref_id == payment_id))
    if exists:
        return False
    db.add(_entry(user_id, credits, "pack", "grant_pack", "payment", payment_id, note))
    await db.flush()
    return True


async def grant_referral(db: AsyncSession, user_id: str, credits: int, ref_id: str, note: str) -> bool:
    """Invite credits (bonus bucket, never expire). Once per referred user per recipient."""
    await ensure_account(db, user_id)
    exists = await db.scalar(select(func.count()).select_from(CreditEntry).where(
        CreditEntry.user_id == user_id, CreditEntry.reason == "grant_referral", CreditEntry.ref_id == ref_id))
    if exists:
        return False
    db.add(_entry(user_id, credits, "bonus", "grant_referral", "referral", ref_id, note))
    await db.flush()
    return True


async def take_back_pack(db: AsyncSession, user_id: str, credits: int, refund_id: str) -> int:
    """A pack was refunded: remove its credits, as far as they're unspent. Returns credits removed."""
    await ensure_account(db, user_id)
    exists = await db.scalar(select(func.count()).select_from(CreditEntry).where(
        CreditEntry.user_id == user_id, CreditEntry.reason == "adjust", CreditEntry.ref_id == refund_id))
    if exists:
        return 0
    remove = min(credits, (await balances(db, user_id))["pack"])
    if remove:
        db.add(_entry(user_id, -remove, "pack", "adjust", "refund", refund_id, "Pack refunded"))
        await db.flush()
    return remove


async def summary(db: AsyncSession, user_id: str) -> dict:
    sub = await ensure_account(db, user_id)
    b = await balances(db, user_id)
    held = await db.scalar(
        select(func.coalesce(func.sum(CreditReservation.amount), 0))
        .where(CreditReservation.user_id == user_id, CreditReservation.status == "held")
    )
    return {
        "plan": sub.plan,
        "balance": sum(b.values()),
        "buckets": b,
        "held": int(held or 0),
        "monthly_credits": C.PLANS.get(sub.plan, C.PLANS[C.DEFAULT_PLAN])["monthly"],
        "resets_at": _aware(sub.current_period_end).isoformat(),
        "status": sub.status,
        "cancel_at_period_end": bool(sub.cancel_at_period_end),
        "can_manage": bool(sub.provider_customer_id),
        "search_credits": {p: C.SEARCH_CREDITS[p] for p in C.LIVE_PLATFORMS},
    }


async def has_finished_run(db: AsyncSession, campaign_id: str) -> bool:
    """Whether this campaign already had a paid search that finished (a new one is "Find more")."""
    found = await db.scalar(
        select(func.count()).select_from(CreditReservation)
        .where(CreditReservation.campaign_id == campaign_id, CreditReservation.status == "committed")
    )
    return bool(found)


async def _release_rows(db: AsyncSession, res: CreditReservation, reason: str, note: str | None = None) -> None:
    for bucket, amount in (res.buckets or {}).items():
        if amount:
            db.add(_entry(res.user_id, int(amount), bucket, reason, "reservation", res.reservation_id, note))


async def reserve(db: AsyncSession, user_id: str, campaign_id: str | None, run_id: str, q: Quote,
                  now: datetime | None = None) -> CreditReservation:
    """Hold the quoted credits for this run. Raises NotEnoughCredits or DailyLimitReached."""
    now = now or _now()
    await ensure_account(db, user_id, now)  # also takes the lock
    started = await db.scalar(
        select(func.count()).select_from(CreditReservation)
        .where(CreditReservation.user_id == user_id, CreditReservation.created_at >= now - timedelta(days=1))
    )
    if (started or 0) >= C.MAX_SEARCHES_PER_DAY:
        raise DailyLimitReached(f"You can start up to {C.MAX_SEARCHES_PER_DAY} searches a day. Try again tomorrow.")

    # A new run of the same campaign cancels the old one (Inngest singleton), so give its credits back.
    if campaign_id:
        old = (await db.execute(
            select(CreditReservation).where(CreditReservation.campaign_id == campaign_id, CreditReservation.status == "held")
        )).scalars().all()
        for res in old:
            await _release_rows(db, res, "release", "Replaced by a new search")
            res.status, res.settled_at = "released", now
        await db.flush()

    b = await balances(db, user_id)
    total = sum(b.values())
    if total < q.credits:
        raise NotEnoughCredits(q.credits, total)
    res = CreditReservation(user_id=user_id, campaign_id=campaign_id, run_id=run_id, amount=q.credits,
                            platforms=q.platforms, status="held", expires_at=now + C.RESERVATION_TTL, buckets={})
    db.add(res)
    await db.flush()
    taken: dict[str, int] = {}
    need = q.credits
    for bucket in C.BUCKETS:
        take = min(need, b[bucket])
        if take:
            taken[bucket] = take
            db.add(_entry(user_id, -take, bucket, "reserve", "reservation", res.reservation_id))
            need -= take
        if not need:
            break
    res.buckets = taken
    await db.flush()
    return res


async def _held(db: AsyncSession, run_id: str) -> CreditReservation | None:
    res = (await db.execute(select(CreditReservation).where(CreditReservation.run_id == run_id))).scalar_one_or_none()
    if res is None or res.status != "held":
        return None
    await lock(db, res.user_id)
    await db.refresh(res)  # re-read under the lock: another worker may have settled it
    return res if res.status == "held" else None


async def settle(db: AsyncSession, run_id: str, creators_found: int, now: datetime | None = None) -> str | None:
    """Finish a run's reservation: keep the credits, or refund them if too few creators were found.

    Idempotent: a retried run settles once. Returns the new status, or None if nothing was held.
    """
    res = await _held(db, run_id)
    if res is None:
        return None
    if creators_found < C.GUARANTEE_MIN_CREATORS:
        await _release_rows(db, res, "refund", f"Only {creators_found} creators found")
        res.status = "refunded"
    else:
        res.status = "committed"
        from app.billing import referrals  # late import: referrals uses this module

        await referrals.grant_after_first_search(db, res.user_id, now)
    res.settled_at = now or _now()
    await db.flush()
    return res.status


async def release(db: AsyncSession, run_id: str, note: str = "Search didn't finish",
                  now: datetime | None = None) -> bool:
    res = await _held(db, run_id)
    if res is None:
        return False
    await _release_rows(db, res, "release", note)
    res.status, res.settled_at = "released", now or _now()
    await db.flush()
    return True


async def release_expired(db: AsyncSession, now: datetime | None = None) -> int:
    now = now or _now()
    run_ids = (await db.execute(
        select(CreditReservation.run_id)
        .where(CreditReservation.status == "held", CreditReservation.expires_at < now)
    )).scalars().all()
    count = 0
    for run_id in run_ids:
        count += await release(db, run_id, "Search timed out", now)
    return count


async def history(db: AsyncSession, user_id: str, limit: int = 50) -> list[dict]:
    rows = (await db.execute(
        select(CreditEntry).where(CreditEntry.user_id == user_id)
        .order_by(CreditEntry.created_at.desc(), CreditEntry.entry_id).limit(limit)
    )).scalars().all()
    return [{"delta": r.delta, "bucket": r.bucket, "reason": r.reason, "note": r.note,
             "at": _aware(r.created_at).isoformat() if r.created_at else None} for r in rows]


async def adjust(db: AsyncSession, user_id: str, delta: int, note: str, ref_id: str) -> None:
    """Manual grant or correction by the team (e.g. support). Goes to the bonus bucket."""
    await ensure_account(db, user_id)
    db.add(_entry(user_id, delta, "bonus", "adjust", "admin", ref_id, note))
    await db.flush()


__all__ = ["grant_referral", "start_paid_period", "change_plan", "set_status", "grant_pack", "take_back_pack", "NotEnoughCredits", "DailyLimitReached", "Quote", "quote", "balances", "ensure_account", "summary",
           "reserve", "settle", "release", "release_expired", "history", "adjust", "has_finished_run",
           "month_bounds"]

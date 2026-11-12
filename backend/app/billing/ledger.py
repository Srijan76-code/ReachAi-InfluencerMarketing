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


async def ensure_account(db: AsyncSession, user_id: str, now: datetime | None = None) -> Subscription:
    """Create the Free plan with welcome credits on first use, and start a new period when one has ended.

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
        db.add(_entry(user_id, C.PLANS[sub.plan]["monthly"], "monthly", "grant_plan", "period", start.isoformat()))
        await db.flush()
        return sub

    if now < _aware(sub.current_period_end):
        return sub

    # The period ended: expire what's left, roll some over on paid plans, then grant the new month.
    plan = C.PLANS.get(sub.plan, C.PLANS[C.DEFAULT_PLAN])
    old_ref = _aware(sub.current_period_start).isoformat()
    left = await balances(db, user_id)
    if left["rollover"]:
        db.add(_entry(user_id, -left["rollover"], "rollover", "expire", "period", old_ref))
    if left["monthly"]:
        db.add(_entry(user_id, -left["monthly"], "monthly", "expire", "period", old_ref))
    start, end = month_bounds(now)
    consecutive = _aware(sub.current_period_end) == start
    if plan["rollover"] and consecutive and left["monthly"]:
        carried = min(left["monthly"], plan["monthly"])
        db.add(_entry(user_id, carried, "rollover", "rollover", "period", start.isoformat(), "Unused credits from last month"))
    sub.current_period_start, sub.current_period_end = start, end
    db.add(_entry(user_id, plan["monthly"], "monthly", "grant_plan", "period", start.isoformat()))
    await db.flush()
    return sub


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


__all__ = ["NotEnoughCredits", "DailyLimitReached", "Quote", "quote", "balances", "ensure_account", "summary",
           "reserve", "settle", "release", "release_expired", "history", "adjust", "has_finished_run",
           "month_bounds"]

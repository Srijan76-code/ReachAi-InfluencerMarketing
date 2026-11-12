import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.billing import constants as C
from app.billing import ledger
from app.models.billing import CreditReservation, Subscription

pytestmark = pytest.mark.asyncio

NOV = datetime(2026, 11, 12, 10, tzinfo=timezone.utc)
DEC = datetime(2026, 12, 3, 10, tzinfo=timezone.utc)
FEB = datetime(2027, 2, 3, 10, tzinfo=timezone.utc)
YT = ledger.quote({})


async def balance(factory, user="u1"):
    async with factory() as db:
        return await ledger.balances(db, user)


async def reserve(factory, run_id, campaign="c1", q=YT, now=NOV, user="u1"):
    async with factory() as db:
        res = await ledger.reserve(db, user, campaign, run_id, q, now=now)
        await db.commit()
        return res


async def test_new_account_gets_free_plan_and_welcome_credits(db):
    async with db() as s:
        data = await ledger.summary(s, "u1")
        await s.commit()
    assert data["plan"] == "free"
    assert data["balance"] == C.WELCOME_CREDITS + C.PLANS["free"]["monthly"]  # 5 + 3
    assert data["buckets"]["bonus"] == 5 and data["buckets"]["monthly"] == 3
    async with db() as s:  # reading again grants nothing more
        assert (await ledger.summary(s, "u1"))["balance"] == 8


async def test_quote_charges_live_platforms_only():
    assert ledger.quote({}).credits == 1
    assert ledger.quote({"campaign": {"platforms": ["youtube", "linkedin"]}}).platforms == ["youtube"]
    assert ledger.quote({"campaign": {"platforms": ["instagram"]}}).platforms == ["youtube"]  # not live yet
    assert ledger.quote({}, find_more=True).credits == 1  # half of 1, rounded up


async def test_reserve_spends_expiring_credits_first(db):
    async with db() as s:
        await ledger.ensure_account(s, "u1", NOV)
        await s.commit()
    big = ledger.Quote(credits=4, platforms=["youtube"], find_more=False)
    res = await reserve(db, "r1", q=big)
    assert res.buckets == {"monthly": 3, "bonus": 1}
    assert await balance(db) == {"monthly": 0, "rollover": 0, "bonus": 4, "pack": 0}


async def test_not_enough_credits_changes_nothing(db):
    too_much = ledger.Quote(credits=9, platforms=["youtube"], find_more=False)
    with pytest.raises(ledger.NotEnoughCredits) as err:
        await reserve(db, "r1", q=too_much)
    assert err.value.needed == 9 and err.value.balance == 8


async def test_commit_keeps_credits_and_settle_is_idempotent(db):
    await reserve(db, "r1")
    async with db() as s:
        assert await ledger.settle(s, "r1", creators_found=25) == "committed"
        await s.commit()
    async with db() as s:  # a retried run settles once
        assert await ledger.settle(s, "r1", creators_found=25) is None
    assert sum((await balance(db)).values()) == 7


async def test_too_few_creators_are_refunded(db):
    await reserve(db, "r1")
    async with db() as s:
        assert await ledger.settle(s, "r1", creators_found=4) == "refunded"
        await s.commit()
    assert sum((await balance(db)).values()) == 8


async def test_failed_or_stale_runs_give_credits_back(db):
    await reserve(db, "r1", campaign="c1")
    await reserve(db, "r2", campaign="c2")
    async with db() as s:
        assert await ledger.release(s, "r1") is True
        assert await ledger.release(s, "r1") is False
        assert await ledger.release_expired(s, NOV + C.RESERVATION_TTL + timedelta(minutes=1)) == 1
        await s.commit()
    assert sum((await balance(db)).values()) == 8
    async with db() as s:
        statuses = {r.run_id: r.status for r in (await s.execute(CreditReservation.__table__.select())).all()}
    assert statuses == {"r1": "released", "r2": "released"}


async def test_rerunning_a_campaign_releases_the_old_hold(db):
    await reserve(db, "r1", campaign="c1")
    await reserve(db, "r2", campaign="c1")
    async with db() as s:
        rows = {r.run_id: r.status for r in (await s.execute(CreditReservation.__table__.select())).all()}
    assert rows == {"r1": "released", "r2": "held"}
    assert sum((await balance(db)).values()) == 7


async def test_daily_limit(db, monkeypatch):
    monkeypatch.setattr(C, "MAX_SEARCHES_PER_DAY", 2)
    await reserve(db, "r1", campaign="c1")
    await reserve(db, "r2", campaign="c2")
    with pytest.raises(ledger.DailyLimitReached):
        await reserve(db, "r3", campaign="c3")


async def test_free_month_expires_and_regrants_without_rollover(db):
    async with db() as s:
        await ledger.ensure_account(s, "u1", NOV)
        await s.commit()
    async with db() as s:
        await ledger.ensure_account(s, "u1", DEC)
        await ledger.ensure_account(s, "u1", DEC)  # same period: nothing more
        await s.commit()
    assert await balance(db) == {"monthly": 3, "rollover": 0, "bonus": 5, "pack": 0}


async def test_paid_plan_without_a_renewal_falls_back_to_free(db):
    async with db() as s:
        await ledger.ensure_account(s, "u1", NOV)
        sub = await s.get(Subscription, "u1")
        sub.plan = "solo"  # set by hand: no payment provider will renew it
        await s.commit()
    async with db() as s:  # December, inside the grace period: waits for the renewal
        await ledger.ensure_account(s, "u1", DEC)
        await s.commit()
        assert (await s.get(Subscription, "u1")).plan == "solo"
    async with db() as s:  # February: lapsed, back on Free with a fresh month
        await ledger.ensure_account(s, "u1", FEB)
        await s.commit()
        assert (await s.get(Subscription, "u1")).plan == "free"
    assert await balance(db) == {"monthly": 3, "rollover": 0, "bonus": 5, "pack": 0}


async def test_users_never_touch_each_others_credits(db):
    await reserve(db, "r1")
    assert sum((await balance(db, "u2")).values()) == 0
    async with db() as s:
        assert (await ledger.summary(s, "u2"))["balance"] == 8


async def test_concurrent_searches_never_overspend(db):
    if db.backend != "postgres":
        pytest.skip("needs Postgres advisory locks")
    five = ledger.Quote(credits=5, platforms=["youtube"], find_more=False)  # balance 8: only one fits

    async def attempt(i):
        try:
            await reserve(db, f"r{i}", campaign=f"c{i}", q=five)
            return True
        except ledger.NotEnoughCredits:
            return False

    results = await asyncio.gather(*(attempt(i) for i in (1, 2, 3)))
    assert results.count(True) == 1
    assert sum((await balance(db)).values()) == 3

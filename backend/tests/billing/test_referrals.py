from datetime import datetime, timedelta, timezone

import pytest

from app.billing import constants as C
from app.billing import ledger, referrals
from app.models.user import User

pytestmark = pytest.mark.asyncio


async def bal(factory, user):
    async with factory() as db:
        return await ledger.balances(db, user)


async def new_user(factory, uid, created=None):
    async with factory() as db:
        db.add(User(user_id=uid, clerk_id=f"clerk-{uid}", created_at=created or datetime.now(timezone.utc)))
        await db.commit()


async def search(factory, user, run_id, found=25, campaign="c1"):
    async with factory() as db:
        await ledger.reserve(db, user, campaign, run_id, ledger.quote({}))
        status = await ledger.settle(db, run_id, found)
        await db.commit()
        return status


async def test_both_get_credits_after_the_new_users_first_real_search(db):
    async with db() as s:
        code = await referrals.code_for(s, "u1")
        assert code == await referrals.code_for(s, "u1")  # stable
        await s.commit()
    await new_user(db, "n1")
    async with db() as s:
        assert await referrals.claim(s, await s.get(User, "n1"), code.upper()) == "u1"  # case-insensitive
        await s.commit()
    assert await search(db, "n1", "r1", found=3) == "refunded"  # too few creators: no reward
    assert (await bal(db, "n1"))["bonus"] == 5 and (await bal(db, "u1"))["bonus"] == 0
    assert await search(db, "n1", "r2") == "committed"
    assert (await bal(db, "n1"))["bonus"] == 5 + C.REFERRAL_CREDITS
    assert (await bal(db, "u1"))["bonus"] == 5 + C.REFERRAL_CREDITS
    await search(db, "n1", "r3", campaign="c2")  # later searches give nothing more
    assert (await bal(db, "u1"))["bonus"] == 5 + C.REFERRAL_CREDITS
    async with db() as s:
        info = await referrals.summary(s, "u1")
    assert info["invited"] == 1 and info["rewarded"] == 1


@pytest.mark.parametrize("case", ["own", "twice", "old", "bad"])
async def test_invites_that_dont_count(db, case):
    async with db() as s:
        code = await referrals.code_for(s, "u1")
        other = await referrals.code_for(s, "u2")
        await s.commit()
    await new_user(db, "n1", created=datetime.now(timezone.utc) - (timedelta(days=30) if case == "old" else timedelta(0)))
    async with db() as s:
        user = await s.get(User, "u1" if case == "own" else "n1")
        if case == "twice":
            await referrals.claim(s, user, code)
            await s.commit()
            code = other
        with pytest.raises(referrals.ReferralError):
            await referrals.claim(s, user, "nope1234" if case == "bad" else code)


async def test_referrer_rewards_are_capped_per_year(db, monkeypatch):
    monkeypatch.setattr(C, "REFERRALS_PER_YEAR", 1)
    async with db() as s:
        code = await referrals.code_for(s, "u1")
        await s.commit()
    for i, uid in enumerate(("n1", "n2")):
        await new_user(db, uid)
        async with db() as s:
            await referrals.claim(s, await s.get(User, uid), code)
            await s.commit()
        await search(db, uid, f"r{i}", campaign=f"c{i + 1}")
    assert (await bal(db, "u1"))["bonus"] == 5 + C.REFERRAL_CREDITS  # only the first counted
    assert (await bal(db, "n2"))["bonus"] == 5 + C.REFERRAL_CREDITS  # the new user still gets theirs

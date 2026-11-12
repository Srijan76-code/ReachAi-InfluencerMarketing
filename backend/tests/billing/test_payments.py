"""Dodo webhooks → plans and credits, and the webhook signature check. No live API calls."""

import base64
import time
from datetime import datetime, timedelta, timezone

import pytest

from app.billing import constants as C
from app.billing import dodo, ledger, webhooks
from app.models.billing import Payment, Subscription

pytestmark = pytest.mark.asyncio

SOLO, PRO = dodo.TEST_PRODUCT_IDS["solo_monthly"], dodo.TEST_PRODUCT_IDS["pro_monthly"]
NOV12 = datetime(2026, 11, 12, 16, 57, tzinfo=timezone.utc)
DEC12 = datetime(2026, 12, 12, 16, 57, tzinfo=timezone.utc)
JAN12 = datetime(2027, 1, 12, 16, 57, tzinfo=timezone.utc)
SECRET = "whsec_" + base64.b64encode(b"reachai-test-secret-0123456789ab").decode()


def sub_event(product=SOLO, start=NOV12, end=DEC12, user="u1", **extra):
    return {"payload_type": "Subscription", "subscription_id": "sub_1", "product_id": product, "status": "active",
            "previous_billing_date": start.isoformat(), "next_billing_date": end.isoformat(),
            "customer": {"customer_id": "cus_1", "email": "f@example.com"},
            "metadata": {"user_id": user, "item": "solo_monthly"} if user else {}, **extra}


def pack_payment(item="pack_10", payment_id="pay_p1", user="u1"):
    return {"payload_type": "Payment", "payment_id": payment_id, "subscription_id": None, "status": "succeeded",
            "total_amount": 800, "currency": "USD", "customer": {"customer_id": "cus_1"},
            "metadata": {"user_id": user, "item": item}}


async def apply(factory, event_type, data):
    async with factory() as db:
        user = await webhooks.handle(db, event_type, data)
        await db.commit()
        return user


async def state(factory, user="u1"):
    async with factory() as db:
        b = await ledger.balances(db, user)
        sub = await db.get(Subscription, user)
        return b, sub


async def start_free(factory, now=datetime(2026, 11, 5, tzinfo=timezone.utc)):
    async with factory() as db:
        await ledger.ensure_account(db, "u1", now)
        await db.commit()


# --- signatures -----------------------------------------------------------------------------------------

def headers(body: bytes, msg_id="msg_1", stamp=None, secret=SECRET):
    stamp = stamp or int(time.time())
    return {"webhook-id": msg_id, "webhook-timestamp": str(stamp),
            "webhook-signature": dodo.sign_for_tests(body, msg_id, stamp, secret)}


async def test_signature_check():
    body = b'{"type":"payment.succeeded"}'
    assert dodo.verify_webhook(body, headers(body), SECRET)
    assert not dodo.verify_webhook(body + b" ", headers(body), SECRET)  # body changed
    other = "whsec_" + base64.b64encode(b"another-secret-another-secret!!").decode()
    assert not dodo.verify_webhook(body, headers(body, secret=other), SECRET)
    assert not dodo.verify_webhook(body, headers(body, stamp=int(time.time()) - 600), SECRET)  # replayed
    assert not dodo.verify_webhook(body, {}, SECRET)
    h = headers(body)
    h["webhook-signature"] = "v1,bogus " + h["webhook-signature"]  # several signatures: any may match
    assert dodo.verify_webhook(body, h, SECRET)


# --- subscriptions --------------------------------------------------------------------------------------

async def test_first_payment_moves_free_user_to_solo(db):
    await start_free(db)
    assert await apply(db, "subscription.active", sub_event()) == "u1"
    b, sub = await state(db)
    assert sub.plan == "solo" and sub.status == "active"
    assert sub.provider_subscription_id == "sub_1" and sub.provider_customer_id == "cus_1"
    assert b == {"monthly": 25, "rollover": 0, "bonus": 5, "pack": 0}  # Free's 3 expired, 25 granted
    await apply(db, "subscription.active", sub_event())  # repeated delivery
    await apply(db, "subscription.renewed", sub_event())  # same period under another name
    assert (await state(db))[0]["monthly"] == 25


async def test_renewal_rolls_unused_credits_over_once(db):
    await start_free(db)
    await apply(db, "subscription.active", sub_event())
    async with db() as s:  # spend 5 of the 25
        await ledger.reserve(s, "u1", "c1", "r1", ledger.Quote(5, ["youtube"], False), now=NOV12 + timedelta(days=1))
        await ledger.settle(s, "r1", 30)
        await s.commit()
    await apply(db, "subscription.renewed", sub_event(start=DEC12, end=JAN12))
    b, sub = await state(db)
    assert b["monthly"] == 25 and b["rollover"] == 20 and _aware(sub.current_period_end) == JAN12
    await apply(db, "subscription.renewed", sub_event())  # the old period arrives late: ignored
    b2, _ = await state(db)
    assert b2 == b


async def test_upgrade_adds_the_difference_and_downgrade_waits(db):
    await start_free(db)
    await apply(db, "subscription.active", sub_event())
    await apply(db, "subscription.plan_changed", sub_event(product=PRO))
    b, sub = await state(db)
    assert sub.plan == "pro" and b["monthly"] == 80  # 25 + 55
    await apply(db, "subscription.plan_changed", sub_event(product=PRO))  # repeated
    assert (await state(db))[0]["monthly"] == 80
    # downgrade applied by Dodo at the next billing date
    await apply(db, "subscription.plan_changed", sub_event(product=SOLO, start=DEC12, end=JAN12))
    b, sub = await state(db)
    assert sub.plan == "solo" and b["monthly"] == 25 and b["rollover"] == 80  # Pro's unused credits roll over (max 80)


async def test_cancelled_plan_keeps_credits_until_period_end_then_free(db):
    await start_free(db)
    await apply(db, "subscription.active", sub_event())
    await apply(db, "subscription.updated", sub_event(cancel_at_next_billing_date=True))
    _, sub = await state(db)
    assert sub.cancel_at_period_end is True and sub.plan == "solo"
    await apply(db, "subscription.cancelled", sub_event(status="cancelled"))
    async with db() as s:
        await ledger.ensure_account(s, "u1", NOV12 + timedelta(days=10))  # still in the paid month
        await s.commit()
    assert (await state(db))[1].plan == "solo"
    async with db() as s:
        await ledger.ensure_account(s, "u1", DEC12 + timedelta(hours=1))
        await s.commit()
    b, sub = await state(db)
    assert sub.plan == "free" and b == {"monthly": 3, "rollover": 0, "bonus": 5, "pack": 0}


async def test_unpaid_renewal_waits_for_grace_then_falls_back_to_free(db):
    await start_free(db)
    await apply(db, "subscription.active", sub_event())
    await apply(db, "subscription.on_hold", sub_event(status="on_hold"))
    assert (await state(db))[1].status == "past_due"
    async with db() as s:
        await ledger.ensure_account(s, "u1", DEC12 + timedelta(days=1))  # within the grace period
        await s.commit()
    assert (await state(db))[1].plan == "solo"
    async with db() as s:
        await ledger.ensure_account(s, "u1", DEC12 + C.RENEWAL_GRACE + timedelta(hours=1))
        await s.commit()
    assert (await state(db))[1].plan == "free"


async def test_events_find_the_user_by_customer_when_metadata_is_missing(db):
    await start_free(db)
    await apply(db, "subscription.active", sub_event())
    await apply(db, "subscription.renewed", sub_event(start=DEC12, end=JAN12, user=None))
    assert _aware((await state(db))[1].current_period_end) == JAN12
    assert await apply(db, "subscription.active", {**sub_event(user="nobody"), "subscription_id": "sub_x",
                                                   "customer": {"customer_id": "cus_x"}}) is None


# --- packs ----------------------------------------------------------------------------------------------

async def test_pack_payment_grants_once_and_refund_takes_back_what_is_left(db):
    await start_free(db)
    await apply(db, "payment.succeeded", pack_payment())
    await apply(db, "payment.succeeded", pack_payment())  # repeated
    b, _ = await state(db)
    assert b["pack"] == 10
    async with db() as s:
        pay = await s.get(Payment, "pay_p1")
        assert pay.kind == "pack" and pay.item == "pack_10" and pay.amount_minor == 800
        # spend everything except 4 pack credits (monthly 3 + bonus 5 first, then 6 pack)
        await ledger.reserve(s, "u1", "c1", "r1", ledger.Quote(14, ["youtube"], False))
        await ledger.settle(s, "r1", 30)
        await s.commit()
    assert (await state(db))[0]["pack"] == 4
    await apply(db, "refund.succeeded", {"payload_type": "Refund", "refund_id": "ref_1", "payment_id": "pay_p1",
                                         "metadata": {"user_id": "u1"}})
    await apply(db, "refund.succeeded", {"payload_type": "Refund", "refund_id": "ref_1", "payment_id": "pay_p1",
                                         "metadata": {"user_id": "u1"}})
    assert (await state(db))[0]["pack"] == 0
    async with db() as s:
        assert (await s.get(Payment, "pay_p1")).status == "refunded"


async def test_subscription_payment_is_recorded_without_granting_pack_credits(db):
    await start_free(db)
    data = {**pack_payment(item="solo_monthly", payment_id="pay_s1"), "subscription_id": "sub_1"}
    await apply(db, "payment.succeeded", data)
    b, _ = await state(db)
    assert b["pack"] == 0
    async with db() as s:
        assert (await s.get(Payment, "pay_s1")).kind == "subscription"


def _aware(dt):
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

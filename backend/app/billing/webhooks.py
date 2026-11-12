"""Turn Dodo webhook events into plan and credit changes (spec §5.4).

Every handler is idempotent: Dodo retries deliveries and may send them out of order, and the route also
skips webhook ids it has already handled. Money never moves here; we only record what Dodo reports.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import constants as C
from app.billing import dodo, ledger
from app.models.billing import Payment, Subscription
from app.models.user import User

logger = logging.getLogger(__name__)

ACTIVE_EVENTS = {"subscription.active", "subscription.renewed"}
TROUBLE_EVENTS = {"subscription.on_hold", "subscription.past_due", "subscription.failed"}
ENDED_EVENTS = {"subscription.cancelled", "subscription.expired"}


def _when(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def _user_for(db: AsyncSession, data: dict) -> str | None:
    """Our user: from the checkout metadata, else from the subscription or customer we stored."""
    user_id = (data.get("metadata") or {}).get("user_id")
    if user_id and await db.get(User, str(user_id)):
        return str(user_id)
    sub_id = data.get("subscription_id")
    customer_id = (data.get("customer") or {}).get("customer_id")
    conds = []
    if sub_id:
        conds.append(Subscription.provider_subscription_id == sub_id)
    if customer_id:
        conds.append(Subscription.provider_customer_id == customer_id)
    if not conds:
        return None
    return await db.scalar(select(Subscription.user_id).where(or_(*conds)).limit(1))


def _item(data: dict) -> str | None:
    item = (data.get("metadata") or {}).get("item")
    if item in C.ITEMS:
        return item
    product = data.get("product_id")
    if not product:
        cart = data.get("product_cart") or []
        product = cart[0].get("product_id") if cart and isinstance(cart[0], dict) else None
    return dodo.item_for_product(product)


def _plan(data: dict) -> str | None:
    # The product decides the plan (a plan change keeps the old checkout metadata).
    item = dodo.item_for_product(data.get("product_id")) or _item(data)
    spec = C.ITEMS.get(item or "")
    return spec["plan"] if spec and spec["kind"] == "plan" else None


async def handle(db: AsyncSession, event_type: str, data: dict) -> str | None:
    """Apply one event. Returns the user it was for (None if it isn't ours or needs nothing)."""
    user_id = await _user_for(db, data)
    if user_id is None:
        logger.warning("Dodo %s: no matching user", event_type)
        return None
    customer_id = (data.get("customer") or {}).get("customer_id")

    if event_type in ACTIVE_EVENTS or event_type == "subscription.plan_changed":
        plan = _plan(data)
        start, end = _when(data.get("previous_billing_date")), _when(data.get("next_billing_date"))
        if not plan or not start or not end:
            logger.warning("Dodo %s for %s: unknown product or dates", event_type, user_id)
            return user_id
        sub = await ledger.ensure_account(db, user_id)
        mid_period = start <= ledger.aware(sub.current_period_start) + C.PERIOD_MATCH
        if event_type == "subscription.plan_changed" and mid_period and sub.plan not in (plan, C.DEFAULT_PLAN):
            await ledger.change_plan(db, user_id, plan, f"{data.get('subscription_id')}:{plan}:{start.isoformat()}")
        await ledger.start_paid_period(db, user_id, plan, start, end, provider_subscription_id=data["subscription_id"],
                                       provider_customer_id=customer_id)
        await ledger.set_status(db, user_id, "active", bool(data.get("cancel_at_next_billing_date")))
    elif event_type == "subscription.updated":
        if data.get("status") == "active":
            await ledger.set_status(db, user_id, "active", bool(data.get("cancel_at_next_billing_date")))
    elif event_type in TROUBLE_EVENTS:
        await ledger.set_status(db, user_id, "past_due")
    elif event_type in ENDED_EVENTS:
        await ledger.set_status(db, user_id, "cancelled", True)
    elif event_type == "payment.succeeded":
        await _payment(db, user_id, data)
    elif event_type == "refund.succeeded":
        await _refund(db, user_id, data)
    elif event_type.startswith("dispute."):
        logger.warning("Dodo %s for user %s on payment %s", event_type, user_id, data.get("payment_id"))
    return user_id


async def _payment(db: AsyncSession, user_id: str, data: dict) -> None:
    payment_id = data.get("payment_id")
    if not payment_id:
        return
    item = _item(data)
    kind = "subscription" if data.get("subscription_id") else "pack"
    if await db.get(Payment, payment_id) is None:
        db.add(Payment(payment_id=payment_id, user_id=user_id, kind=kind, item=item,
                       amount_minor=data.get("total_amount"), currency=data.get("currency"), status="succeeded"))
    spec = C.ITEMS.get(item or "")
    if kind == "pack" and spec and spec["kind"] == "pack":
        await ledger.grant_pack(db, user_id, spec["credits"], payment_id, f"{spec['credits']} credits")
    await db.flush()


async def _refund(db: AsyncSession, user_id: str, data: dict) -> None:
    payment = await db.get(Payment, data.get("payment_id") or "")
    if payment is None:
        return
    payment.status = "refunded"
    spec = C.ITEMS.get(payment.item or "")
    if payment.kind == "pack" and spec and spec["kind"] == "pack":
        await ledger.take_back_pack(db, user_id, spec["credits"], data.get("refund_id") or payment.payment_id)
    await db.flush()

"""Credits for the signed-in user (spec §5.5). Payments come later (F2.2)."""

import json
import logging
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.campaign_runs import quote_for
from app.auth.user import get_db_user
from app.billing import constants as C
from app.billing import dodo, ledger, webhooks
from app.db.database import get_db
from app.models.billing import BillingEvent
from app.models.campaign import Campaign
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()
webhook_router = APIRouter()  # no sign-in: Dodo calls it, the signature proves it


@router.get("/balance")
async def balance(user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    data = await ledger.summary(db, user.user_id)
    await db.commit()  # first read creates the Free plan and welcome credits
    data["payments"] = bool(dodo.api_key() and dodo.product_ids() and dodo.can_buy(user.clerk_id))
    return data


@router.get("/history")
async def history(user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    await ledger.ensure_account(db, user.user_id)
    await db.commit()
    return {"entries": await ledger.history(db, user.user_id)}


@router.get("/quote/{campaign_id}")
async def quote(campaign_id: str, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """What starting (or re-running) this campaign's search costs, and the balance, shown before Run."""
    campaign = (await db.execute(
        select(Campaign).where(Campaign.campaign_id == campaign_id, Campaign.user_id == user.user_id)
    )).scalar_one_or_none()
    if campaign is None:
        raise HTTPException(404, "Campaign not found")
    q = await quote_for(db, campaign, campaign.campaign_details or {})
    data = await ledger.summary(db, user.user_id)
    await db.commit()
    return {"credits": q.credits, "platforms": q.platforms, "find_more": q.find_more,
            "balance": data["balance"], "enough": data["balance"] >= q.credits}


# --- payments (Dodo, spec §5.4) ----------------------------------------------------------------------------

class CheckoutIn(BaseModel):
    item: str


async def _clerk_contact(clerk_id: str) -> tuple[str | None, str | None]:
    """The user's email and name from Clerk, to prefill checkout. Best effort: None if unavailable."""
    secret = os.getenv("CLERK_SECRET_KEY")
    if not secret:
        return None, None
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.get(f"https://api.clerk.com/v1/users/{clerk_id}",
                                    headers={"Authorization": f"Bearer {secret}"})
        if resp.status_code != 200:
            return None, None
        data = resp.json()
        primary = data.get("primary_email_address_id")
        emails = data.get("email_addresses") or []
        email = next((e.get("email_address") for e in emails if e.get("id") == primary), None)
        name = " ".join(p for p in (data.get("first_name"), data.get("last_name")) if p) or None
        return email, name
    except (httpx.HTTPError, ValueError):
        return None, None


def _app_url(request: Request) -> str:
    return (os.getenv("APP_URL") or str(request.base_url)).rstrip("/")


@router.post("/checkout")
async def checkout(body: CheckoutIn, request: Request, user: User = Depends(get_db_user),
                   db: AsyncSession = Depends(get_db)):
    """Start buying a plan or pack. Returns a checkout URL for the payment popup, or changes an existing
    paid plan directly (upgrade now, downgrade from the next billing date)."""
    spec = C.ITEMS.get(body.item)
    if spec is None:
        raise HTTPException(400, "Unknown item")
    product_id = dodo.product_ids().get(body.item)
    if not dodo.api_key() or not product_id or not dodo.can_buy(user.clerk_id):
        raise HTTPException(503, "Payments aren't open yet")
    sub = await ledger.ensure_account(db, user.user_id)
    await db.commit()
    paid_active = sub.plan != C.DEFAULT_PLAN and sub.status in ("active", "past_due") and sub.provider_subscription_id
    try:
        if spec["kind"] == "plan" and paid_active:
            if sub.plan == spec["plan"]:
                raise HTTPException(409, "You're already on this plan")
            upgrade = C.PLANS[spec["plan"]]["monthly"] > C.PLANS[sub.plan]["monthly"]
            await dodo.change_plan(sub.provider_subscription_id, product_id, upgrade=upgrade)
            return {"changed": True, "effective": "now" if upgrade else "next_billing_date", "plan": spec["plan"]}
        email, name = (None, None) if sub.provider_customer_id else await _clerk_contact(user.clerk_id)
        url = await dodo.create_checkout(
            product_id, user_id=user.user_id, item=body.item,
            return_url=f"{_app_url(request)}/pricing?checkout=done",
            customer_id=sub.provider_customer_id, email=email, name=name,
        )
    except dodo.DodoError as err:
        logger.error("Dodo checkout failed for %s: %s", user.user_id, err)
        raise HTTPException(502, "Couldn't open checkout. Try again in a minute.") from err
    return {"checkout_url": url, "mode": dodo.mode()}


@router.post("/portal")
async def portal(request: Request, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """A link to Dodo's customer portal: invoices, card, cancel."""
    sub = await ledger.ensure_account(db, user.user_id)
    await db.commit()
    if not sub.provider_customer_id:
        raise HTTPException(404, "No paid plan yet")
    try:
        return {"url": await dodo.portal_link(sub.provider_customer_id, f"{_app_url(request)}/pricing")}
    except dodo.DodoError as err:
        logger.error("Dodo portal failed for %s: %s", user.user_id, err)
        raise HTTPException(502, "Couldn't open billing settings. Try again in a minute.") from err


@webhook_router.post("/api/webhooks/dodo")
async def dodo_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    secret = dodo.webhook_key()
    if not secret:
        raise HTTPException(503, "Webhooks aren't set up")
    body = await request.body()
    headers = {k: request.headers.get(k, "") for k in ("webhook-id", "webhook-timestamp", "webhook-signature")}
    if not dodo.verify_webhook(body, headers, secret):
        raise HTTPException(401, "Invalid signature")
    try:
        event = json.loads(body)
    except ValueError as err:
        raise HTTPException(400, "Invalid JSON") from err
    event_id, event_type = headers["webhook-id"], str(event.get("type") or "")
    if await db.get(BillingEvent, event_id):
        return {"received": True, "duplicate": True}
    try:
        user_id = await webhooks.handle(db, event_type, event.get("data") or {})
        db.add(BillingEvent(event_id=event_id, type=event_type, user_id=user_id))
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Dodo webhook %s (%s) failed; Dodo will retry", event_id, event_type)
        raise HTTPException(500, "Processing failed")
    return {"received": True}

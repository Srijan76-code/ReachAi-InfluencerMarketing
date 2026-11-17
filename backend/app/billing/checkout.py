"""Opening a checkout for a plan or pack, shared by the website route and the agent's `buy_credits` tool."""

from __future__ import annotations

import os

import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import constants as C
from app.billing import dodo, ledger


async def clerk_contact(clerk_id: str) -> tuple[str | None, str | None]:
    """The user's email and name from Clerk, to prefill checkout. Best effort: None if unavailable."""
    secret = os.getenv("CLERK_SECRET_KEY")
    if not secret:
        return None, None
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.get(f"https://api.clerk.com/v1/users/{clerk_id}", headers={"Authorization": f"Bearer {secret}"})
        if resp.status_code != 200:
            return None, None
        data = resp.json()
        primary = data.get("primary_email_address_id")
        email = next((e.get("email_address") for e in (data.get("email_addresses") or []) if e.get("id") == primary), None)
        name = " ".join(p for p in (data.get("first_name"), data.get("last_name")) if p) or None
        return email, name
    except (httpx.HTTPError, ValueError):
        return None, None


def can_open_checkout(item: str, clerk_id: str) -> str:
    """The product id for `item`, or raises (400 unknown item, 503 payments not open for this person yet)."""
    if C.ITEMS.get(item) is None:
        raise HTTPException(400, "Unknown item")
    product_id = dodo.product_ids().get(item)
    if not dodo.api_key() or not product_id or not dodo.can_buy(clerk_id):
        raise HTTPException(503, "Payments aren't open yet")
    return product_id


async def open_checkout(db: AsyncSession, user_id: str, clerk_id: str, item: str, product_id: str, return_url: str,
                        contact=clerk_contact) -> str:
    """A checkout URL for a new purchase. `contact(clerk_id)` → (email, name) to prefill. Raises HTTPException(502) when
    the payment provider fails."""
    sub = await ledger.ensure_account(db, user_id)
    email, name = (None, None) if sub.provider_customer_id else await contact(clerk_id)
    try:
        return await dodo.create_checkout(product_id, user_id=user_id, item=item, return_url=return_url,
                                          customer_id=sub.provider_customer_id, email=email, name=name)
    except dodo.DodoError as err:
        raise HTTPException(502, "Couldn't open checkout. Try again in a minute.") from err

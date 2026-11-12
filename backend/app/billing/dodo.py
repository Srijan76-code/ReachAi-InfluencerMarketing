"""Dodo Payments (merchant of record): checkout sessions, plan changes, the customer portal and webhook checks.

Dodo only collects money. Plans and credits live in our ledger (spec §5.4), so switching providers stays a
change in this file. Docs: https://docs.dodopayments.com (checkout sessions, webhooks follow Standard Webhooks).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URLS = {"test_mode": "https://test.dodopayments.com", "live_mode": "https://live.dodopayments.com"}
TIMEOUT = httpx.Timeout(15.0, connect=5.0)
SIGNATURE_TOLERANCE_SECONDS = 5 * 60

# Products made in Dodo test mode (not secret). Live ids come from DODO_PRODUCT_IDS.
TEST_PRODUCT_IDS = {
    "solo_monthly": "pdt_0NrnfGgYHDlqzddbQalav",
    "pro_monthly": "pdt_0NrnfGsHnzb22LF7IuzMg",
    "pack_10": "pdt_0NrnfH5Og5xUvxUzSb3W6",
    "pack_30": "pdt_0NrnfHFDcl5TzbbqEh0uO",
}


class DodoError(Exception):
    """A call to Dodo failed. The message is safe to log, never to show raw to users."""


class NotConfigured(DodoError):
    pass


def environment() -> str:
    env = os.getenv("DODO_PAYMENTS_ENVIRONMENT", "test_mode")
    return env if env in BASE_URLS else "test_mode"


def mode() -> str:
    """What the browser checkout SDK calls it: "test" or "live"."""
    return "live" if environment() == "live_mode" else "test"


def api_key() -> str | None:
    return os.getenv("DODO_PAYMENTS_API_KEY") or None


def webhook_key() -> str | None:
    return os.getenv("DODO_PAYMENTS_WEBHOOK_KEY") or None


def product_ids() -> dict[str, str]:
    raw = os.getenv("DODO_PRODUCT_IDS")
    if raw:
        try:
            ids = json.loads(raw)
            if isinstance(ids, dict):
                return {str(k): str(v) for k, v in ids.items()}
        except ValueError:
            logger.error("DODO_PRODUCT_IDS is not valid JSON; using test products")
    return dict(TEST_PRODUCT_IDS) if environment() == "test_mode" else {}


def item_for_product(product_id: str | None) -> str | None:
    return next((item for item, pid in product_ids().items() if pid == product_id), None)


async def _call(method: str, path: str, *, json_body: dict | None = None, params: dict | None = None) -> dict[str, Any]:
    key = api_key()
    if not key:
        raise NotConfigured("DODO_PAYMENTS_API_KEY is not set")
    async with httpx.AsyncClient(base_url=BASE_URLS[environment()], timeout=TIMEOUT) as client:
        try:
            resp = await client.request(method, path, json=json_body, params=params,
                                        headers={"Authorization": f"Bearer {key}"})
        except httpx.HTTPError as exc:
            raise DodoError(f"{method} {path}: {type(exc).__name__}") from exc
    if resp.status_code >= 400:
        raise DodoError(f"{method} {path}: HTTP {resp.status_code} {resp.text[:300]}")
    return resp.json() if resp.content else {}


async def create_checkout(product_id: str, *, user_id: str, item: str, return_url: str,
                          customer_id: str | None = None, email: str | None = None, name: str | None = None) -> str:
    body: dict[str, Any] = {
        "product_cart": [{"product_id": product_id, "quantity": 1}],
        "metadata": {"user_id": user_id, "item": item},
        "return_url": return_url,
        "minimal_address": True,
    }
    if customer_id:
        body["customer"] = {"customer_id": customer_id}
    elif email:
        body["customer"] = {"email": email, **({"name": name} if name else {})}
    data = await _call("POST", "/checkouts", json_body=body)
    url = data.get("checkout_url")
    if not url:
        raise DodoError("checkout session has no checkout_url")
    return url


async def change_plan(subscription_id: str, product_id: str, *, upgrade: bool) -> None:
    """Upgrade now (charge the prorated difference, keep the old plan if that payment fails), or
    downgrade from the next billing date (no charge)."""
    body: dict[str, Any] = {"product_id": product_id, "quantity": 1}
    if upgrade:
        body.update(proration_billing_mode="prorated_immediately", effective_at="immediately",
                    on_payment_failure="prevent_change")
    else:
        body.update(proration_billing_mode="do_not_bill", effective_at="next_billing_date")
    await _call("POST", f"/subscriptions/{subscription_id}/change-plan", json_body=body)


async def portal_link(customer_id: str, return_url: str) -> str:
    data = await _call("POST", f"/customers/{customer_id}/customer-portal/session", params={"return_url": return_url})
    link = data.get("link")
    if not link:
        raise DodoError("portal session has no link")
    return link


def verify_webhook(body: bytes, headers: dict[str, str], secret: str, now: float | None = None) -> bool:
    """Standard Webhooks check: HMAC-SHA256 over "{id}.{timestamp}.{body}" with the endpoint's secret.

    The secret is shown in Dodo as "whsec_<base64>". The signature header holds one or more "v1,<base64>"
    values; any match is valid. Old or future timestamps (> 5 minutes) are refused to stop replays.
    """
    msg_id = headers.get("webhook-id") or ""
    stamp = headers.get("webhook-timestamp") or ""
    sigs = headers.get("webhook-signature") or ""
    if not (msg_id and stamp and sigs and secret):
        return False
    try:
        sent_at = int(stamp)
    except ValueError:
        return False
    if abs((now or time.time()) - sent_at) > SIGNATURE_TOLERANCE_SECONDS:
        return False
    raw = secret[len("whsec_"):] if secret.startswith("whsec_") else secret
    try:
        key = base64.b64decode(raw)
    except ValueError:
        return False
    expected = base64.b64encode(hmac.new(key, f"{msg_id}.{stamp}.".encode() + body, hashlib.sha256).digest()).decode()
    for part in sigs.split():
        version, _, sig = part.partition(",")
        if version == "v1" and hmac.compare_digest(sig, expected):
            return True
    return False


def sign_for_tests(body: bytes, msg_id: str, stamp: int, secret: str) -> str:
    raw = secret[len("whsec_"):] if secret.startswith("whsec_") else secret
    digest = hmac.new(base64.b64decode(raw), f"{msg_id}.{stamp}.".encode() + body, hashlib.sha256).digest()
    return "v1," + base64.b64encode(digest).decode()

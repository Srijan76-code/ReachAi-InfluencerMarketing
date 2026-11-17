"""account_status, connect_gmail and buy_credits: the person-only steps as links an agent can hand over (F9.8, 8a).
No Google, Dodo or Clerk calls happen here."""

from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException

from tests.mcp.conftest import call_tool, make_key

pytestmark = pytest.mark.asyncio


@pytest.fixture
def world(monkeypatch):
    """Gmail and payments as fakes; each test changes what it needs."""
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "client-secret")
    w = SimpleNamespace(gmail=None, open=True, opened=[])

    async def account_for(db, user_id):
        return w.gmail

    async def open_checkout(db, user_id, clerk_id, item, product_id, return_url, contact=None):
        w.opened.append((item, return_url))
        return f"https://pay.example/{item}"

    def can_open(item, clerk_id):
        if not w.open:
            raise HTTPException(503, "Payments aren't open yet")
        return f"prod_{item}"

    monkeypatch.setattr("app.gmail.service.account_for", account_for)
    monkeypatch.setattr("app.billing.dodo.api_key", lambda: "key" if w.open else None)
    monkeypatch.setattr("app.billing.dodo.can_buy", lambda clerk_id: w.open)
    monkeypatch.setattr("app.billing.checkout.open_checkout", open_checkout)
    monkeypatch.setattr("app.billing.checkout.can_open_checkout", can_open)
    return w


async def test_account_status_says_what_is_missing_and_what_to_do(client, db, world):
    out = await call_tool(client, await make_key(db), "account_status")
    d = out["structuredContent"]
    assert d["gmail"]["connected"] is False and d["payments_open"] is True and d["campaigns"] >= 1
    assert d["credits"]["plan"] and "balance" in d["credits"]
    assert any(s.get("tool") == "connect_gmail" for s in d["next_steps"])
    assert "not connected" in out["content"][0]["text"]


async def test_account_status_when_gmail_is_connected_and_payments_are_closed(client, db, world):
    world.gmail = SimpleNamespace(email="founder@example.com", status="active")
    world.open = False
    d = (await call_tool(client, await make_key(db), "account_status"))["structuredContent"]
    assert d["gmail"]["connected"] is True and d["gmail"]["email"] == "founder@example.com" and d["payments_open"] is False
    assert not any(s.get("tool") == "connect_gmail" for s in d["next_steps"])


async def test_connect_gmail_returns_a_google_link_bound_to_this_founder_only(client, db, world):
    out = await call_tool(client, await make_key(db), "connect_gmail", campaign_id="c1")
    d = out["structuredContent"]
    q = parse_qs(urlsplit(d["url"]).query)
    assert urlsplit(d["url"]).netloc == "accounts.google.com" and q["client_id"] == ["client-id"]
    assert q["redirect_uri"][0].endswith("/api/gmail/callback") and "access_type" in q
    from app.gmail import crypto

    state = crypto.verify_state(q["state"][0])
    assert state["u"] == "u1" and state["r"] == "/campaign/c1/outreach"  # tied to this account; returns to the campaign
    other = await call_tool(client, await make_key(db), "connect_gmail", campaign_id="other")
    assert other["isError"] is True and "not found" in other["content"][0]["text"].lower()


async def test_connect_gmail_when_the_server_has_no_google_app(client, db, world, monkeypatch):
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET")
    out = await call_tool(client, await make_key(db), "connect_gmail")
    assert out["isError"] is True and "isn't set up" in out["content"][0]["text"]


async def test_buy_credits_returns_a_link_and_charges_nothing(client, db, world):
    out = await call_tool(client, await make_key(db), "buy_credits", item="pack_10")
    assert out["structuredContent"]["checkout_url"] == "https://pay.example/pack_10" and "10 credits" in out["content"][0]["text"]
    assert world.opened == [("pack_10", world.opened[0][1])] and world.opened[0][1].endswith("/pricing?checkout=done")


async def test_buy_credits_refuses_when_payments_are_closed_and_for_unknown_items(client, db, world):
    world.open = False
    closed = await call_tool(client, await make_key(db), "buy_credits", item="pack_10")
    assert closed["isError"] is True and "aren't open" in closed["content"][0]["text"] and world.opened == []
    bad = await call_tool(client, await make_key(db), "buy_credits", item="pack_999")
    assert bad["isError"] is True


async def test_buy_credits_never_changes_an_existing_paid_plan(client, db, world):
    from sqlalchemy import select

    from app.models.billing import Subscription

    token = await make_key(db)
    await call_tool(client, token, "account_status")  # makes the account row
    async with db() as s:
        sub = (await s.execute(select(Subscription).where(Subscription.user_id == "u1"))).scalar_one()
        sub.plan, sub.status, sub.provider_subscription_id = "solo", "active", "sub_1"
        await s.commit()
    out = await call_tool(client, token, "buy_credits", item="pro_monthly")
    assert out["isError"] is True and "already on a paid plan" in out["content"][0]["text"] and world.opened == []
    packs = await call_tool(client, token, "buy_credits", item="pack_30")  # a pack is still fine
    assert packs["structuredContent"]["checkout_url"].endswith("pack_30")

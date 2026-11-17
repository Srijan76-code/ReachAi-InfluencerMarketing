"""account_status, connect_gmail, buy_credits: the one-time steps that need a person, as links an agent can hand over (F9.8).

An agent can't create an account, can't pass Google's consent screen and must never charge a card. So these tools
report what is missing and return the link the founder opens once. Nothing here changes an account or takes money."""

from __future__ import annotations

import os
from typing import Annotated, Literal, Optional

from fastapi import HTTPException
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, ToolAnnotations
from pydantic import Field
from sqlalchemy import func, select

from app.billing import checkout as checkout_mod
from app.billing import constants as C
from app.billing import dodo, ledger
from app.gmail import client as GC
from app.gmail import constants as G
from app.gmail import crypto, service as GS
from app.mcp import format as fmt
from app.mcp.auth import current_user_id
from app.mcp.config import app_url
from app.mcp.db import session_scope
from app.mcp.tools import _owned_campaign
from app.models.campaign import Campaign
from app.models.user import User

READS = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
LINKS = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=False, open_world_hint=True)


def _gmail_redirect() -> str:
    return os.getenv("GOOGLE_OAUTH_REDIRECT_URI") or f"{app_url()}{G.CALLBACK_PATH}"


def register_account_tools(server: MCPServer) -> None:
    @server.tool(
        title="Account status",
        description=(
            "What is set up on the founder's ReachAI account and what is blocking: credits and plan, whether Gmail is "
            "connected, whether payments are open, how many campaigns exist, and the next steps with the tool or link "
            "for each. Call it first in a new session."
        ),
        annotations=READS,
    )
    async def account_status() -> CallToolResult:
        user_id = current_user_id()
        async with session_scope() as db:
            account = await ledger.summary(db, user_id)
            await db.commit()
            gmail = await GS.account_for(db, user_id)
            clerk_id = await db.scalar(select(User.clerk_id).where(User.user_id == user_id))
            campaigns = await db.scalar(select(func.count()).select_from(Campaign).where(Campaign.user_id == user_id)) or 0
        connected = bool(gmail)
        needs_reconnect = bool(gmail and getattr(gmail, "status", "active") != "active")
        payments_open = bool(dodo.api_key() and dodo.can_buy(clerk_id or ""))
        steps = []
        if not campaigns:
            steps.append({"do": "Make a campaign", "tool": "read_website, then create_campaign"})
        if account["balance"] < 1:
            steps.append({"do": "Get credits to run a search" + (" (payments aren't open yet)" if not payments_open else ""),
                          "tool": "buy_credits" if payments_open else None, "link": f"{app_url()}/pricing"})
        if not connected or needs_reconnect:
            steps.append({"do": "Connect Gmail so ReachAI can send and read mail" if not connected else "Reconnect Gmail",
                          "tool": "connect_gmail"})
        data = {
            "credits": {"balance": account["balance"], "plan": account["plan"], "monthly_credits": account["monthly_credits"],
                        "resets_at": account["resets_at"], "search_credits": account["search_credits"]},
            "gmail": {"configured": GC.configured(), "connected": connected, "needs_reconnect": needs_reconnect,
                      "email": gmail.email if gmail else None, "daily_cap": G.DAILY_SEND_CAP},
            "payments_open": payments_open, "campaigns": campaigns, "next_steps": steps, "app": app_url(),
        }
        lines = [
            f"**Credits:** {account['balance']} ({account['plan']} plan, {account['monthly_credits']} a month, resets {account['resets_at'][:10]})",
            f"**Gmail:** " + (f"connected as {gmail.email}" + (" (needs reconnecting)" if needs_reconnect else "") if connected else "not connected"),
            f"**Payments:** {'open' if payments_open else 'not open yet'} · **Campaigns:** {campaigns}",
        ]
        if steps:
            lines += ["", "Next:"] + [f"- {s['do']}" + (f" → {s['tool']}" if s.get("tool") else "") for s in steps]
        lines += ["", f"Open ReachAI: {app_url()}"]
        return fmt.result("\n".join(lines), data)

    @server.tool(
        title="Connect Gmail",
        description=(
            "Get the link where the founder connects their Gmail (Google asks them to agree: it needs a person, you can't "
            "do it for them). Give them the link and tell them to open it. ReachAI then sends and reads mail from their "
            "own address. Check account_status afterwards to see that it worked."
        ),
        annotations=LINKS,
    )
    async def connect_gmail(
        campaign_id: Annotated[Optional[str], Field(description="Optional: the campaign to return to afterwards.")] = None,
    ) -> CallToolResult:
        user_id = current_user_id()
        if not GC.configured():
            raise ToolError("Gmail isn't set up on this ReachAI server yet.")
        async with session_scope() as db:
            if campaign_id:
                await _owned_campaign(db, campaign_id, user_id)
            existing = await GS.account_for(db, user_id)
        back = f"/campaign/{campaign_id}/outreach" if campaign_id else "/campaign"
        url = GC.auth_url(_gmail_redirect(), crypto.sign_state(user_id, back), login_hint=existing.email if existing else None)
        already = bool(existing and getattr(existing, "status", "active") == "active")
        text = ((f"Gmail is already connected as {existing.email}. " if already else "")
                + "Give the founder this link and ask them to open it and agree on Google's page. It expires in 10 minutes and is "
                  f"only for their account. Then call account_status to check.\n\n{url}")
        return fmt.result(text, {"url": url, "already_connected": already, "expires_in_minutes": 10})

    @server.tool(
        title="Buy credits",
        description=(
            "Get a checkout link for a credit pack or a plan. You never pay: give the founder the link and they pay on the "
            "payment page. Only searches use credits. Changing an existing paid plan is done by the founder in ReachAI "
            f"({app_url()}/pricing), not from here."
        ),
        annotations=LINKS,
    )
    async def buy_credits(
        item: Annotated[Literal["pack_10", "pack_30", "solo_monthly", "pro_monthly"], Field(description="pack_10 = 10 credits, pack_30 = 30 credits, solo_monthly / pro_monthly = a plan.")],
    ) -> CallToolResult:
        user_id = current_user_id()
        async with session_scope() as db:
            clerk_id = await db.scalar(select(User.clerk_id).where(User.user_id == user_id))
            try:
                product_id = checkout_mod.can_open_checkout(item, clerk_id or "")
            except HTTPException as exc:
                raise ToolError("Payments aren't open for this account yet." if exc.status_code == 503 else str(exc.detail))
            sub = await ledger.ensure_account(db, user_id)
            await db.commit()
            if C.ITEMS[item]["kind"] == "plan" and sub.plan != C.DEFAULT_PLAN and sub.status in ("active", "past_due") and sub.provider_subscription_id:
                raise ToolError(f"The founder is already on a paid plan. Changing plans is done in ReachAI: {app_url()}/pricing")
            try:
                url = await checkout_mod.open_checkout(db, user_id, clerk_id or "", item, product_id, f"{app_url()}/pricing?checkout=done")
            except HTTPException as exc:
                raise ToolError(str(exc.detail))
        label = C.ITEMS[item]
        what = f"{label['credits']} credits" if label["kind"] == "pack" else f"the {label['plan']} plan"
        return fmt.result(f"Checkout for {what}. Give the founder this link; nothing is charged until they pay on that page, "
                          f"and credits appear within a minute of paying.\n\n{url}", {"checkout_url": url, "item": item, "mode": dodo.mode()})

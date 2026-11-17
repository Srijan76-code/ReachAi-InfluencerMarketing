"""send_message: the founder's agent sends a draft it wrote, after the founder's yes in chat (F9.7, step 3b).

Two steps, like start_search: `confirm=false` shows exactly what would go out and returns a preview token; after the
founder agrees the agent calls again with `confirm=true` and that token. Sending then goes through the same claim and
Gmail path as the app's Approve button (one send per draft, the daily Gmail cap, suppression lists, the timeline).

The server cannot know whether the founder really said yes, so the guards are around it: the campaign switch ("Allow
my agent to send", off by default), a signed token that only matches the exact text, address and subject shown, 10
agent sends a day, an email and a bell line for every send, and a refusal to agree, close or send anything the agent
didn't write and ReachAI check."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from fastapi import HTTPException
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, ToolAnnotations
from pydantic import Field
from sqlalchemy import select

from app.agent import constants as A
from app.agent import grants
from app.agent import queue as Q
from app.agent.autopilot import notify_agent_send, settings_of
from app.mcp import format as fmt
from app.mcp.auth import current_user_id
from app.mcp.db import session_scope
from app.mcp.tools import CampaignId, _owned_campaign
from app.models.campaign import Campaign
from app.models.deal import AgentProposal, CreatorDeal, DealEvent

logger = logging.getLogger(__name__)

SENDS_EMAIL = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=True)


def _key() -> bytes:
    from app.gmail import crypto

    return hashlib.sha256(b"reachai-send-preview:" + crypto._secret()).digest()


def _digest(p: AgentProposal, d: CreatorDeal, subject: Optional[str]) -> str:
    """What the founder was shown: if any of it changes, the token no longer fits."""
    pl = p.payload or {}
    body = json.dumps({"p": p.proposal_id, "text": (pl.get("message") or "").strip(), "to": d.contact_email, "subject": subject or "",
                       "kind": p.kind, "terms": pl.get("terms")}, sort_keys=True, default=str)
    return hashlib.sha256(body.encode()).hexdigest()


def make_token(p: AgentProposal, d: CreatorDeal, subject: Optional[str], *, now: Optional[float] = None) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"d": _digest(p, d, subject), "t": int(now or time.time())}).encode()).decode()
    return payload + "." + hmac.new(_key(), payload.encode(), hashlib.sha256).hexdigest()


def check_token(token: Optional[str], p: AgentProposal, d: CreatorDeal, subject: Optional[str], *, now: Optional[float] = None) -> None:
    """Raises a ToolError that says what to do when the token is missing, forged, old or for different text."""
    again = "Call send_message with confirm=false to get a new preview, show it to the founder, and ask again."
    if not token or "." not in token:
        raise ToolError("Sending needs the preview token from send_message with confirm=false. " + again)
    payload, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, hmac.new(_key(), payload.encode(), hashlib.sha256).hexdigest()):
        raise ToolError("That preview token isn't valid. " + again)
    try:
        info = json.loads(base64.urlsafe_b64decode(payload.encode()))
    except ValueError:
        raise ToolError("That preview token isn't valid. " + again)
    if (now or time.time()) - info.get("t", 0) > A.SEND_PREVIEW_MINUTES * 60:
        raise ToolError(f"That preview is older than {A.SEND_PREVIEW_MINUTES} minutes. " + again)
    if info.get("d") != _digest(p, d, subject):
        raise ToolError("The draft, the address or the subject changed since the preview (the founder may have edited it). " + again)


def _brand(campaign: Campaign) -> str:
    return (((campaign.campaign_details or {}).get("brand") or {}).get("name")) or "Working together"


async def _sent_by_agent_today(db, user_id: str, *, first_emails: bool, campaign_id: Optional[str] = None) -> int:
    """Messages the founder's agent sent today (UTC) of one class (first emails, or replies and follow-ups), across the
    founder's campaigns or in one."""
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    q = select(CreatorDeal.deal_id).join(Campaign, Campaign.campaign_id == CreatorDeal.campaign_id).where(Campaign.user_id == user_id)
    if campaign_id:
        q = q.where(CreatorDeal.campaign_id == campaign_id)
    ids = (await db.execute(q)).scalars().all()
    if not ids:
        return 0
    rows = (await db.execute(select(DealEvent.payload).where(
        DealEvent.deal_id.in_(ids), DealEvent.type == "message_sent", DealEvent.created_at >= start))).scalars().all()
    return sum(1 for payload in rows if (payload or {}).get("agent") and ((payload or {}).get("kind") == "pitch") == first_emails)


async def _find(db, campaign: Campaign, deal_id: str):
    """(deal, lead, the draft the agent may send). Raises a ToolError that says what to do instead."""
    deal = (await db.execute(select(CreatorDeal).where(CreatorDeal.deal_id == deal_id,
                                                       CreatorDeal.campaign_id == campaign.campaign_id))).scalar_one_or_none()
    if deal is None:
        raise ToolError("Conversation not found in this campaign. Use inbox to see the deal ids.")
    lead = next((l for l in (campaign.campaign_leads or []) if isinstance(l, dict) and str(l.get("id")) == deal.creator_id), {})
    pending = list((await db.execute(select(AgentProposal).where(AgentProposal.deal_id == deal.deal_id, AgentProposal.status == "pending")
                                     .order_by(AgentProposal.created_at.desc()))).scalars())
    sendable = [p for p in pending if p.kind in (*A.AGENT_SEND_KINDS, "pitch") and (p.payload or {}).get("message")]
    if not sendable:
        if any(p.kind in A.DECISION_KINDS for p in pending):
            raise ToolError("Agreeing a price and closing a deal always need the founder in ReachAI. Tell them it is waiting there.")
        raise ToolError("There is no draft to send on this conversation. Write one with reply_context and submit_reply first.")
    p = sendable[0]
    pl = p.payload or {}
    if pl.get("source") != "agent":
        raise ToolError("Only drafts your agent wrote (and ReachAI checked) can be sent from here. The founder sends this one in ReachAI.")
    if pl.get("held") or pl.get("needs_review") or pl.get("problems"):
        raise ToolError("This draft didn't pass ReachAI's checks, so the founder has to read it first in ReachAI.")
    return deal, lead, p


def register_send_tools(server: MCPServer) -> None:
    @server.tool(
        title="Send a reply",
        description=(
            "Send a reply or follow-up YOU wrote (and ReachAI checked) from the founder's Gmail. Two steps: FIRST call "
            "with confirm=false: it returns exactly what would be sent (to, subject, text, price) and a preview_token. "
            "SHOW THAT TO THE FOUNDER AND ASK. Only after they clearly say yes call again with confirm=true and the "
            "token. Never confirm on your own, and never in an unattended or scheduled run. Works only if the founder "
            "turned on 'Allow my agent to send' for the campaign; at most 10 sends a day. Agreeing a price, closing a "
            "deal are never sent from here. First emails need their own permission (send_first_emails)."
        ),
        annotations=SENDS_EMAIL,
    )
    async def send_message(
        campaign_id: CampaignId,
        deal_id: Annotated[str, Field(description="The deal id from inbox.")],
        confirm: Annotated[bool, Field(description="Set true only after the founder said yes to the preview.")] = False,
        preview_token: Annotated[Optional[str], Field(description="The token from the confirm=false call.")] = None,
    ) -> CallToolResult:
        from app.gmail import service as GS
        from app.outreach.drafts import auto_channel

        user_id = current_user_id()
        async with session_scope() as db:
            campaign = await _owned_campaign(db, campaign_id, user_id)
            s = settings_of(campaign.outreach_settings)
            deal, lead, p = await _find(db, campaign, deal_id)
            first = p.kind == "pitch"
            if first:  # a first email: needs its own permission from the founder
                g = await grants.active(db, user_id, "send_first_emails", campaign_id)
                if g is None:
                    raise ToolError("Sending first emails needs the founder's permission. Call request_permission with ability "
                                    "'send_first_emails' for this campaign and give them the link.")
                mode, per_day, ends = g.mode, g.per_day or 10, g.valid_until
                cap = min(per_day, 20)
            else:
                if s.writer != "agent" or not s.agent_send:
                    raise ToolError("Sending by your agent is off for this campaign. The founder turns it on in ReachAI (Outreach > "
                                    "Autopilot > 'My agent writes replies', then 'Allow my agent to send'), or approves it for you: call "
                                    "request_permission with ability 'send_replies' and give them the link.")
                ends = None
                if s.agent_send_grant:
                    from app.models.agent_grant import AgentGrant

                    g = await db.get(AgentGrant, s.agent_send_grant)
                    if not grants.is_active(g):
                        raise ToolError("The permission to send ended. Ask for a new one with request_permission (ability 'send_replies').")
                    ends = g.valid_until
                mode, per_day = s.agent_send_mode, s.agent_send_per_day
                cap = min(per_day or A.AGENT_SENDS_PER_DAY, A.AGENT_SENDS_PER_DAY)
            account = await GS.account_for(db, user_id)
            if not GS.usable(account):
                raise ToolError("The founder's Gmail isn't connected (or needs reconnecting). Tell them to connect it in ReachAI: use connect_gmail.")
            if not deal.contact_email or auto_channel(deal, lead) != "email":
                raise ToolError("This creator has no email route, so it can't be sent from here. The founder sends it as a DM in ReachAI.")
            pl = p.payload or {}
            if first and ((lead.get("contact") or {}).get("contacted_before")):
                raise ToolError("The founder wrote to this address recently in another campaign, so they decide in ReachAI.")
            used = await _sent_by_agent_today(db, user_id, first_emails=first)
            used_here = await _sent_by_agent_today(db, user_id, first_emails=first, campaign_id=campaign_id)
            if used >= (20 if first else A.AGENT_SENDS_PER_DAY) or used_here >= cap:
                raise ToolError(f"Today's limit for messages sent by your agent here is reached ({used_here} of {cap}). "
                                "The founder can send in ReachAI, or try tomorrow.")
            subject = None if deal.gmail_thread_id else ((pl.get("subject") or "").strip() or _brand(campaign))
            name = (lead.get("title") or deal.creator_name or "the creator")
            preview = {"to": deal.contact_email, "creator": name, "subject": subject or "(reply in the same thread)",
                       "text": pl["message"].strip(), "kind": p.kind, "terms": pl.get("terms"), "sent_today_by_agent": used_here,
                       "daily_limit": cap, "mode": mode, "permission_ends": ends.isoformat() if ends else None}
            if not confirm:
                token = make_token(p, deal, subject)
                if mode == "unattended":
                    how = (f"The founder allowed sending without asking each time (up to {cap} a day), so you may confirm now if it "
                           "looks right. Don't confirm anything that is odd or off-brief.")
                else:
                    how = ("Show it to the founder and ask if you should send it. Only after a clear yes, call send_message again "
                           "with confirm=true and preview_token.")
                text = (f"NOT SENT. This is exactly what would go to {name} ({deal.contact_email}):\n\n{pl['message'].strip()}\n\n"
                        f"{how} The token is valid for {A.SEND_PREVIEW_MINUTES} minutes and only for this text.")
                return fmt.result(text, {**preview, "sent": False, "preview_token": token})

            check_token(preview_token, p, deal, subject)
            pid, did = p.proposal_id, deal.deal_id

            async def send(text: str) -> dict:
                return await GS.send_for_deal(db, account, deal, text, subject=subject)

            if not await Q.claim(db, p):
                raise ToolError("This draft was already sent or handled.")
            try:
                await Q.approve(db, p, deal, None, send=send, subject=subject, agent=True)
                await db.commit()
            except HTTPException as e:
                await db.rollback()
                await Q.release(db, pid)
                raise ToolError(f"Not sent: {e.detail}")
            except Exception:  # noqa: BLE001 - nothing was sent or saved
                logger.exception("agent send failed for deal %s", did)
                await db.rollback()
                await Q.release(db, pid)
                raise ToolError("Sending failed and nothing was sent. Try again in a minute.")
            await notify_agent_send(db, account, name=name, text=pl["message"].strip(), campaign_id=campaign_id)
        return fmt.result(f"Sent to {name}. It is in their chat in ReachAI, marked as sent by your agent, and the founder was emailed.",
                          {**preview, "sent": True, "sent_today_by_agent": used_here + 1})

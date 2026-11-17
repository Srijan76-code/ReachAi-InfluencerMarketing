"""Agent requests that the founder confirms in the app (spec §15.5, roadmap F9.5): send a message, agree a price,
mark a creator paid.

None of these acts. Each one checks the request in code and leaves it for the founder:
- `request_send`: a reply in the creator's chat, in the message box, waiting for the founder's Send.
- `request_agree`: a price and a message in the chat as "Send and agree". The price is held to the same hard limits as
  ReachAI's reply agent (15% over the fair range at most, never above the budget left, never below our last offer).
- `request_mark_paid`: a note on the creator's row in Track's "To pay", with the amount filled in. ReachAI never moves
  money; the founder pays the creator and then clicks Mark paid.
Agent-written messages are never sent by autopilot (`app/agent/autopilot.hold_reason`).
"""

from typing import Annotated, Any, Literal, Optional

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, ToolAnnotations
from pydantic import Field
from sqlalchemy import select

from app.agent import constants as A
from app.deals import constants as DC
from app.mcp import format as fmt
from app.mcp.auth import current_user_id
from app.mcp.db import session_scope
from app.mcp.drafts import check_message
from app.mcp.tools import CampaignId, CreatorId, _find_lead, _owned_campaign
from app.models.deal import AgentProposal, CreatorDeal, DealEvent
from app.tracking import constants as T

REQUEST = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False)

SEND_KEY = "agent:reply"
AGREE_KEY = "agent:agree"
PAID_KEY = "agent:paid"
OPEN_STAGES = ("contacted", "negotiating")
NOTE_CHARS = 300

DealType = Literal["flat", "fee_plus_commission", "commission_only"]


async def _deal(db, campaign_id: str, creator_id: str) -> CreatorDeal:
    deal = (await db.execute(select(CreatorDeal).where(
        CreatorDeal.campaign_id == campaign_id, CreatorDeal.creator_id == creator_id))).scalar_one_or_none()
    if deal is None:
        raise ToolError("This creator isn't in Outreach yet. Start with save_draft for a first message.")
    return deal


async def _events(db, deal: CreatorDeal) -> list:
    return list((await db.execute(select(DealEvent).where(DealEvent.deal_id == deal.deal_id))).scalars())


async def _own_proposal(db, deal: CreatorDeal, key: str) -> Optional[AgentProposal]:
    """Our pending request for this deal, to replace. Refuses while ReachAI or the founder has another message
    waiting in the chat: only one draft shows in the message box, so the founder handles that one first."""
    pending = list((await db.execute(select(AgentProposal).where(
        AgentProposal.deal_id == deal.deal_id, AgentProposal.status.in_(("pending", "sending"))))).scalars())
    for p in pending:
        if p.key != key and p.kind in A.MESSAGE_KINDS and (p.payload or {}).get("message"):
            raise ToolError("Another message is already waiting for the founder in this creator's chat. "
                            "Ask them to send or discard it in ReachAI first.")
    mine = next((p for p in pending if p.key == key), None)
    if mine is not None and mine.status != "pending":
        raise ToolError("The founder is handling your earlier request right now. Try again in a moment.")
    return mine


def _save(db, deal: CreatorDeal, mine: Optional[AgentProposal], *, key: str, kind: str, title: str, reason: str,
          payload: dict) -> tuple[AgentProposal, bool]:
    if mine is not None:
        mine.title, mine.reason, mine.payload = title, reason, payload
        return mine, True
    p = AgentProposal(campaign_id=deal.campaign_id, deal_id=deal.deal_id, key=key, kind=kind, status="pending",
                      title=title, reason=reason, payload=payload)
    db.add(p)
    return p, False


async def _budget_left(db, deal: CreatorDeal, details: dict) -> Optional[float]:
    budget = ((details or {}).get("campaign") or {}).get("budget_total")
    if not budget:
        return None
    rows = (await db.execute(select(CreatorDeal.agreed_rate).where(
        CreatorDeal.campaign_id == deal.campaign_id, CreatorDeal.deal_id != deal.deal_id,
        CreatorDeal.stage.in_(DC.COMMITTED_STAGES)))).scalars().all()
    return float(budget) - float(sum(r or 0 for r in rows))


def price_problems(fee: Optional[int], commission_pct: float, limits) -> list[str]:
    """The reply agent's hard price limits (app/replies/context.Limits), for a price an agent asks to agree."""
    from app.replies import constants as R

    out = []
    if fee is None and not commission_pct:
        out.append("Give a fee, a commission, or both.")
    if fee is not None:
        if limits.ceiling is None:
            out.append("ReachAI has no fair price for this creator yet, so no fee can be agreed from an agent. "
                       "The founder can set a fair range in the app.")
        elif fee > limits.ceiling:
            out.append(f"${fee:,} is over this creator's hard limit of ${limits.ceiling:,} "
                       "(15% over the fair range, and never above the budget left).")
        if fee < R.MIN_FEE:
            out.append(f"A fee under ${R.MIN_FEE} isn't a real offer.")
        if limits.floor is not None and fee < limits.floor:
            out.append(f"${fee:,} is below the ${limits.floor:,} already offered to them: never go back down.")
    if commission_pct > limits.max_commission:
        out.append(f"Commission is capped at {limits.max_commission:g}%.")
    return out


def register_action_tools(server: MCPServer) -> None:
    @server.tool(
        title="Ask the founder to send a reply",
        description=(
            "Write a reply to a creator the founder is already talking to. ReachAI checks it and puts it in the "
            "creator's chat, in the message box. Nothing is sent: the founder reads it and presses Send in ReachAI. "
            "Do not state a price: for a price, use request_agree. Saving again replaces your earlier request."
        ),
        annotations=REQUEST,
    )
    async def request_send(
        campaign_id: CampaignId,
        creator_id: CreatorId,
        message: Annotated[str, Field(description="The full reply, ready to send.")],
    ) -> CallToolResult:
        user_id = current_user_id()
        async with session_scope() as db:
            campaign = await _owned_campaign(db, campaign_id, user_id)
            lead = _find_lead(campaign, creator_id)
            deal = await _deal(db, campaign_id, creator_id)
            if not any(e.type == "message_sent" for e in await _events(db, deal)):
                raise ToolError("Nothing has been sent to this creator yet. Use save_draft for the first message.")
            if deal.stage == "lost":
                raise ToolError("This deal is closed. The founder can reopen it in ReachAI.")
            allowed = (float(deal.agreed_rate),) if deal.stage in DC.COMMITTED_STAGES and deal.agreed_rate else ()
            errors = check_message(message, allowed_amounts=allowed)
            if errors:
                raise ToolError("The reply needs changes before it can be saved:\n- " + "\n- ".join(errors))
            mine = await _own_proposal(db, deal, SEND_KEY)
            body = message.strip()
            proposal, replaced = _save(
                db, deal, mine, key=SEND_KEY, kind="reply", title="Reply from your agent",
                reason="Written by your connected agent. ReachAI checked it. Nothing has been sent.",
                payload={"message": body, "source": "agent", "held": "from_agent"},
            )
            await db.commit()
            ids = {"deal_id": deal.deal_id, "proposal_id": proposal.proposal_id}
        text = (
            f"Reply {'updated' if replaced else 'saved'} in {fmt.cell(lead.get('title'), 60)}'s chat. "
            "**Nothing has been sent.** The founder reads it and presses Send in ReachAI.\n"
            f"Open in ReachAI: {fmt.campaign_link(campaign_id, 'outreach')}"
        )
        return fmt.result(text, {"saved": True, "replaced": replaced, **ids})

    @server.tool(
        title="Ask the founder to agree a price",
        description=(
            "Propose agreeing a price with a creator who is negotiating, with the message that says so. ReachAI "
            "checks the price against the creator's hard limit (15% over the fair range at most, never above the "
            "budget left, never below an earlier offer) and the message (it may only state this price). It appears "
            "in the creator's chat as \"Send and agree\". Nothing is agreed or sent until the founder confirms in "
            "ReachAI. Get the fair range from list_deals or pitch_context first."
        ),
        annotations=REQUEST,
    )
    async def request_agree(
        campaign_id: CampaignId,
        creator_id: CreatorId,
        fee_usd: Annotated[Optional[int], Field(description="The fixed fee in US dollars. Leave out for commission only.", ge=0)],
        message: Annotated[str, Field(description="The message to the creator that agrees this price.")],
        commission_pct: Annotated[float, Field(description="Commission on sales or signups, in %. 0 for none.", ge=0, le=100)] = 0,
    ) -> CallToolResult:
        from app.negotiation import context as X
        from app.replies.context import deal_facts

        user_id = current_user_id()
        async with session_scope() as db:
            campaign = await _owned_campaign(db, campaign_id, user_id)
            lead = _find_lead(campaign, creator_id)
            deal = await _deal(db, campaign_id, creator_id)
            if deal.stage not in OPEN_STAGES:
                raise ToolError(f"This deal is {deal.stage}: a price can only be agreed while you're still talking.")
            events = await _events(db, deal)
            budget_left = await _budget_left(db, deal, campaign.campaign_details or {})
            _, limits = deal_facts(deal, X.facts(deal, events, budget_left=budget_left), budget_left=budget_left)
            commission = float(commission_pct or 0)
            errors = price_problems(fee_usd, commission, limits)
            errors += check_message(message, allowed_amounts=(float(fee_usd),) if fee_usd else ())
            if errors:
                raise ToolError("The request needs changes before it can be saved:\n- " + "\n- ".join(errors))
            mine = await _own_proposal(db, deal, AGREE_KEY)
            deal_type = "commission_only" if fee_usd is None else "fee_plus_commission" if commission else "flat"
            offer = X.Offer(fee_usd, commission)
            payload: dict[str, Any] = {
                "message": message.strip(), "source": "agent", "held": "from_agent", "agreed_rate": float(fee_usd or 0),
                "deal_type": deal_type, "terms": {"fee": fee_usd, "commission_pct": commission},
            }
            if commission:
                payload["commission_pct"] = commission
            proposal, replaced = _save(
                db, deal, mine, key=AGREE_KEY, kind="agree", title=f"Agree {offer.words()}",
                reason="Your connected agent suggests agreeing this price. ReachAI checked it against the hard limit.",
                payload=payload,
            )
            await db.commit()
            ids = {"deal_id": deal.deal_id, "proposal_id": proposal.proposal_id}
        text = (
            f"Request to agree **{offer.words()}** with {fmt.cell(lead.get('title'), 60)} "
            f"{'updated' if replaced else 'saved'}. **Nothing is agreed or sent** until the founder presses "
            "\"Send and agree\" in ReachAI.\n"
            f"Open in ReachAI: {fmt.campaign_link(campaign_id, 'outreach')}"
        )
        return fmt.result(text, {"saved": True, "replaced": replaced, "fee_usd": fee_usd, "commission_pct": commission,
                                 "hard_limit_usd": limits.ceiling, **ids})

    @server.tool(
        title="Ask the founder to mark a creator paid",
        description=(
            "After the founder has paid a creator outside ReachAI, ask them to record it. The amount, method and "
            "note show on the creator's row in Track > To pay, ready for the founder to click Mark paid. ReachAI "
            "never moves money, and nothing is recorded until the founder confirms."
        ),
        annotations=REQUEST,
    )
    async def request_mark_paid(
        campaign_id: CampaignId,
        creator_id: CreatorId,
        amount_usd: Annotated[Optional[float], Field(description="Amount paid. Leave out to use the agreed price.", gt=0)] = None,
        method: Annotated[Optional[Literal[T.PAY_METHODS]], Field(description="How it was paid.")] = None,  # type: ignore[valid-type]
        note: Annotated[Optional[str], Field(description="A reference such as the transaction id.")] = None,
    ) -> CallToolResult:
        user_id = current_user_id()
        async with session_scope() as db:
            campaign = await _owned_campaign(db, campaign_id, user_id)
            lead = _find_lead(campaign, creator_id)
            deal = await _deal(db, campaign_id, creator_id)
            if deal.stage == "paid" or deal.paid_at:
                raise ToolError("This creator is already marked paid.")
            if deal.stage not in DC.COMMITTED_STAGES or not deal.agreed_rate:
                raise ToolError("There's no agreed price with this creator yet, so there's nothing to pay.")
            amount = round(float(amount_usd or deal.agreed_rate), 2)
            if amount > float(deal.agreed_rate) * 1.5:
                raise ToolError(f"${amount:,.2f} is far above the agreed ${deal.agreed_rate:,.0f}. Check the amount.")
            pending = (await db.execute(select(AgentProposal).where(
                AgentProposal.deal_id == deal.deal_id, AgentProposal.key == PAID_KEY))).scalar_one_or_none()
            payload = {"stage": "paid", "amount": amount, "method": method,
                       "note": (note or "").strip()[:NOTE_CHARS] or None, "source": "agent"}
            title = f"Mark paid (${amount:,.2f})"
            reason = "Your connected agent says this creator was paid. Check it, then click Mark paid."
            if pending is None:
                pending = AgentProposal(campaign_id=campaign_id, deal_id=deal.deal_id, key=PAID_KEY, kind="mark_paid",
                                        status="pending", title=title, reason=reason, payload=payload)
                db.add(pending)
                replaced = False
            else:
                pending.status, pending.title, pending.reason, pending.payload = "pending", title, reason, payload
                replaced = True
            await db.commit()
            ids = {"deal_id": deal.deal_id, "proposal_id": pending.proposal_id}
        text = (
            f"Payment of **${amount:,.2f}** to {fmt.cell(lead.get('title'), 60)} is waiting for the founder in "
            "Track > To pay. **Nothing is recorded** until they click Mark paid.\n"
            f"Open in ReachAI: {fmt.campaign_link(campaign_id, 'track')}"
        )
        return fmt.result(text, {"saved": True, "replaced": replaced, "amount_usd": amount, **ids})

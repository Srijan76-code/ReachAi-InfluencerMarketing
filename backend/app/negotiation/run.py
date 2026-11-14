"""Running the negotiation agent for one deal and turning its result into a suggestion in To do."""

from __future__ import annotations

import logging
import statistics
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.costs import CostContext
from app.deals import constants as C
from app.deals import negotiation as N
from app.negotiation import context as X
from app.negotiation import graph as G
from app.negotiation import write as W
from app.models.deal import AgentProposal, CreatorDeal, DealEvent

MARKET_MIN_DEALS = 5
OPT_OUT_FROM = 0.8  # "please stop emailing me": never contacted again (by anyone on ReachAI)
HOLD_FROM = 0.5  # a question or terms only the founder can answer: autopilot waits for them
AGENT_DOWN = "ReachAI couldn't read this reply right now. Read it yourself, or press Suggest again in a minute."
logger = logging.getLogger(__name__)


async def _market(db: AsyncSession, d: CreatorDeal) -> Optional[str]:
    """What creators of a similar size agreed on ReachAI (anonymous, only with enough deals)."""
    if not d.typical_views:
        return None
    rows = (await db.execute(select(CreatorDeal.agreed_rate).where(
        CreatorDeal.agreed_rate.is_not(None), CreatorDeal.stage.in_(C.COMMITTED_STAGES), CreatorDeal.deal_id != d.deal_id,
        CreatorDeal.typical_views.between(d.typical_views * 0.5, d.typical_views * 2)))).scalars().all()
    if len(rows) < MARKET_MIN_DEALS:
        return None
    q = statistics.quantiles(sorted(rows), n=4)
    return f"{len(rows)} creators of a similar size agreed ${q[0]:,.0f}–${q[2]:,.0f} on ReachAI"


async def _committed_elsewhere(db: AsyncSession, d: CreatorDeal) -> float:
    rows = (await db.execute(select(CreatorDeal.agreed_rate).where(
        CreatorDeal.campaign_id == d.campaign_id, CreatorDeal.deal_id != d.deal_id,
        CreatorDeal.stage.in_(C.COMMITTED_STAGES)))).scalars().all()
    return float(sum(r or 0 for r in rows))


async def _inputs(db: AsyncSession, d: CreatorDeal, lead: dict, details: dict, reply_text: str):
    events = list((await db.execute(select(DealEvent).where(DealEvent.deal_id == d.deal_id))).scalars())
    committed = await _committed_elsewhere(db, d)
    budget = ((details or {}).get("campaign") or {}).get("budget_total")
    facts = X.facts(d, events, budget_left=(float(budget) - committed) if budget else None)
    st, fees, pcts = X.state(d, events, lead, details, facts, reply_text, market=await _market(db, d), committed=committed)
    return events, facts, st, fees, pcts


async def _stale_suggestions(db: AsyncSession, d: CreatorDeal) -> None:
    for p in (await db.execute(select(AgentProposal).where(AgentProposal.deal_id == d.deal_id, AgentProposal.status == "pending",
                                                           AgentProposal.key.like("nego:%")))).scalars():
        p.status = "stale"


async def _opted_out(db: AsyncSession, d: CreatorDeal, reply: DealEvent, user_id: str) -> dict:
    """They asked not to be contacted: suppress the address, stop every pending message, ask the founder to close."""
    from app.contacts.ledger import record_contact, suppress

    reason = "They asked not to be contacted again. ReachAI won't email them."
    reply.payload = {**(reply.payload or {}), "agent": {"action": "lost", "reasons": [reason]}, "opt_out": True}
    await _stale_suggestions(db, d)
    for p in (await db.execute(select(AgentProposal).where(AgentProposal.deal_id == d.deal_id,
                                                           AgentProposal.status == "pending"))).scalars():
        p.status = "stale"  # no follow-up, no counter: nothing more goes to them
    if d.contact_email:
        await suppress(db, d.contact_email, "opt_out")
        await record_contact(db, user_id, d.contact_email, d.campaign_id, outcome="opted_out")
    db.add(DealEvent(deal_id=d.deal_id, type="opted_out", payload={}))
    db.add(AgentProposal(campaign_id=d.campaign_id, deal_id=d.deal_id, key=f"nego:{reply.event_id}", kind="mark_lost",
                         status="pending", title="Mark lost", reason=reason, payload={"stage": "lost", "opt_out": True}))
    return {"action": "lost", "reasons": [reason]}


def _held(answers: dict, out: dict) -> Optional[str]:
    """Why autopilot shouldn't send this reply by itself: terms only the founder decides, or a question the
    drafted reply doesn't clearly answer."""
    if float(answers.get("needs_human", 0) or 0) >= HOLD_FROM:
        return "needs_human"
    answered = ((out.get("check") or {}).get("answers") or 0) >= 0.7 and out.get("source") == "ai"
    if float(answers.get("asks_question", 0) or 0) >= HOLD_FROM and not answered:
        return "question"
    return None


def _name(d: CreatorDeal, lead: dict) -> str:
    return (lead or {}).get("first_name") or N.greeting_name((lead or {}).get("title") or d.creator_name)


async def negotiate(db: AsyncSession, d: CreatorDeal, reply: DealEvent, *, lead: dict, details: dict, user_id: str) -> dict:
    """Runs the agent on the creator's latest message (`reply`), records what they asked for, and adds the
    suggested next step (replacing an older pending one). The caller commits. → {"action", "reasons"}"""
    text = (reply.payload or {}).get("text") or ""
    events, facts, st, fees, pcts = await _inputs(db, d, lead, details, text)
    current = X.current_offer(d, facts)
    agreed = current if d.stage in C.COMMITTED_STAGES and d.agreed_rate is not None else None
    try:
        out = await G.run({"jev_state": st, "fee_options": fees, "pct_options": pcts, "facts": facts, "name": _name(d, lead),
                           "context": CostContext(user_id=user_id, campaign_id=d.campaign_id),
                           "current_fee": current.fee if current else None, "agreed": agreed})
    except Exception:
        # Jev or the model is down: the reply is still saved and shown; the founder is told to read it themselves
        logger.exception("negotiation agent failed for deal %s", d.deal_id)
        reason = AGENT_DOWN
        reply.payload = {**(reply.payload or {}), "agent": {"action": "none", "reasons": [reason], "error": True}}
        await _stale_suggestions(db, d)  # a new reply makes the older suggestion out of date either way
        return {"action": "none", "reasons": [reason]}
    decision, ask = out["decision"], out.get("ask")
    answers = out.get("answers") or {}
    if float(answers.get("opt_out", 0) or 0) >= OPT_OUT_FROM:
        return await _opted_out(db, d, reply, user_id)

    if agreed is not None and ask:
        # after agreeing, a new ask doesn't change the deal: it's flagged for the founder (hold or accept)
        reply.payload = {**(reply.payload or {}), "their_ask": {"fee": ask.fee, "commission_pct": ask.commission_pct}}
        if decision.action == "hold":
            reply.payload["change"] = {"from": {"fee": agreed.fee, "commission_pct": agreed.commission_pct},
                                       "to": {"fee": ask.fee, "commission_pct": ask.commission_pct}}
    elif ask:
        # what they asked for, as read by Jev from the amounts in their message
        reply.payload = {**(reply.payload or {}), "their_ask": {"fee": ask.fee, "commission_pct": ask.commission_pct}}
        if ask.fee is not None and ask.fee != d.quoted_rate:
            db.add(DealEvent(deal_id=d.deal_id, type="quoted_rate", payload={"from": d.quoted_rate, "to": ask.fee, "commission_pct": ask.commission_pct}))
            d.quoted_rate = float(ask.fee)
        d.quoted_commission_pct = ask.commission_pct or None
        if d.stage == "contacted":
            db.add(DealEvent(deal_id=d.deal_id, type="stage", payload={"from": "contacted", "to": "negotiating"}))
            d.stage = "negotiating"
    reply.payload = {**(reply.payload or {}), "agent": {"action": decision.action, "reasons": decision.reasons}}

    await _stale_suggestions(db, d)
    if decision.action not in ("counter", "agree", "lost", "hold"):
        return {"action": decision.action, "reasons": decision.reasons}

    o = decision.offer
    terms = {"fee": o.fee, "commission_pct": o.commission_pct, "structure": decision.structure} if o else None
    payload = {"message": out.get("message"), "source": out.get("source", "template"), "terms": terms, "final": decision.final,
               **({"held": h} if (h := _held(answers, out)) else {}),
               "amounts": ({"base": o.fee, "commission_pct": o.commission_pct} if o and o.commission_pct and o.fee else
                           {"counter": o.fee} if o and o.fee else None)}
    if decision.action == "agree":
        kind, title = "agree", f"Agree to {o.words()}"
        payload.update({"stage": "agreed", "agreed_rate": o.fee or 0,
                        "deal_type": "base_plus_commission" if o.commission_pct and o.fee else "affiliate" if o.commission_pct else "flat",
                        "commission_pct": o.commission_pct or None})
    elif decision.action == "hold":
        kind, title = "hold_terms", f"Keep the agreed {o.words()}"
        payload["change"] = reply.payload.get("change")
    elif decision.action == "lost":
        kind, title = "mark_lost", "Close politely and mark lost"
        payload.update({"stage": "lost", "amounts": None, "terms": None})
    else:
        kind, title = "send_counter", f"{'Final offer' if decision.final else 'Offer'}: {o.words()}"
    db.add(AgentProposal(campaign_id=d.campaign_id, deal_id=d.deal_id, key=f"nego:{reply.event_id}", kind=kind, status="pending",
                         title=title, reason=" ".join(decision.reasons), payload=payload))
    return {"action": decision.action, "reasons": decision.reasons}


async def reword(db: AsyncSession, p: AgentProposal, d: CreatorDeal, *, lead: dict, details: dict, user_id: str) -> tuple[str, str]:
    """Another wording of a suggestion's message, same terms, same checks. → (message, source)"""
    pl = dict(p.payload or {})
    reply = (await db.execute(select(DealEvent).where(DealEvent.deal_id == d.deal_id, DealEvent.type == "creator_reply")
                              .order_by(DealEvent.created_at.desc()).limit(1))).scalar_one_or_none()
    _, _, st, _, _ = await _inputs(db, d, lead, details, (reply.payload or {}).get("text", "") if reply else "")
    t = pl.get("terms") or {}
    offer = X.Offer(t.get("fee"), float(t.get("commission_pct") or 0)) if t else None
    action = {"agree": "agree", "mark_lost": "lost", "hold_terms": "hold"}.get(p.kind, "counter")
    text = await W.draft(st, action, offer, t.get("structure", "flat"), "none", bool(pl.get("final")), _name(d, lead),
                         CostContext(user_id=user_id, campaign_id=d.campaign_id),
                         feedback="the founder wants a different wording with the same terms")
    if text and W.numbers_ok(text, offer if action != "lost" else None):
        pl["message"], pl["source"] = text, "ai"
        p.payload = pl
        return text, "ai"
    return pl.get("message") or "", "template"

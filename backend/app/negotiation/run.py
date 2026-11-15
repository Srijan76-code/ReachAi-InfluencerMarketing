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


def _name(d: CreatorDeal, lead: dict) -> str:
    return (lead or {}).get("first_name") or N.greeting_name((lead or {}).get("title") or d.creator_name)


async def _context(db: AsyncSession, d: CreatorDeal, lead: dict, details: dict, *, user_id: str, text: str, mode: str):
    from app.replies import context as RC

    events = list((await db.execute(select(DealEvent).where(DealEvent.deal_id == d.deal_id))).scalars())
    budget = ((details or {}).get("campaign") or {}).get("budget_total")
    budget_left = (float(budget) - await _committed_elsewhere(db, d)) if budget else None
    return await RC.build(db, d, lead, details, user_id=user_id, creator_message=text, events=events,
                          budget_left=budget_left, mode=mode)


# what the reply agent decided → the action shown on their message (the chat and the founder's email read it)
SHOWN_ACTION = {"opt_out": "lost", "wait": "wait", "new_contact": "new_contact", "ask_founder": "ask_founder"}
HELD_FOR = {"hold": "check_failed", "ask_founder": "ask_founder"}


def _terms(price) -> Optional[dict]:
    if price is None:
        return None
    structure = "fee_plus_commission" if price.fee and price.commission_pct else "commission" if price.commission_pct else "flat"
    return {"fee": price.fee, "commission_pct": float(price.commission_pct or 0), "structure": structure}


def _amounts(price) -> Optional[dict]:
    if price is None or not price.fee:
        return None
    return {"base": price.fee, "commission_pct": price.commission_pct} if price.commission_pct else {"counter": price.fee}


async def negotiate(db: AsyncSession, d: CreatorDeal, reply: DealEvent, *, lead: dict, details: dict, user_id: str,
                    agent=None, send_mail=None) -> dict:
    """Runs the reply agent (app/replies/agent.py) on the creator's latest message (`reply`), records what they
    asked for, and adds the next step (replacing an older pending one). The caller commits. → {"action", "reasons"}"""
    from app.replies import agent as RA
    from app.replies import ask as ASK

    text = (reply.payload or {}).get("text") or ""
    try:
        async with db.begin_nested():  # a failed read here must not abort the transaction that saves their reply
            ctx = await _context(db, d, lead, details, user_id=user_id, text=text, mode="reply")
        r = await (agent or RA.reply)(ctx, context=CostContext(user_id=user_id, campaign_id=d.campaign_id))
    except Exception:
        logger.exception("reply agent failed for deal %s", d.deal_id)
        r = None
    if r is None or (r.outcome == "hold" and r.draft is None):
        # can't read or write it right now: the reply is still saved and shown; the founder reads it themselves
        reason = r.reason if r is not None else AGENT_DOWN
        reply.payload = {**(reply.payload or {}), "agent": {"action": "none", "reasons": [reason], "error": r is None}}
        await _stale_suggestions(db, d)
        return {"action": "none", "reasons": [reason]}
    if r.outcome == "opt_out":
        return await _opted_out(db, d, reply, user_id)

    if r.failed:
        from app.replies.memory import note_failures

        await note_failures(db, user_id, r.failed)  # a check this founder's drafts keep failing becomes a lesson
    draft = r.draft
    agreed = d.stage in C.COMMITTED_STAGES and d.agreed_rate is not None
    ask = draft.their_ask if draft is not None and "ask_read" not in r.failed else None
    if ask is not None and (ask.fee is not None or ask.commission_pct):
        reply.payload = {**(reply.payload or {}), "their_ask": {"fee": ask.fee, "commission_pct": ask.commission_pct}}
        if agreed:
            reply.payload["change"] = {"from": {"fee": int(d.agreed_rate), "commission_pct": float(d.commission_pct or 0)},
                                       "to": {"fee": ask.fee, "commission_pct": float(ask.commission_pct or 0)}}
        else:
            if ask.fee is not None and ask.fee != d.quoted_rate:
                db.add(DealEvent(deal_id=d.deal_id, type="quoted_rate", payload={"from": d.quoted_rate, "to": ask.fee,
                                                                                 "commission_pct": ask.commission_pct}))
                d.quoted_rate = float(ask.fee)
            d.quoted_commission_pct = ask.commission_pct or None
            if d.stage == "contacted":
                db.add(DealEvent(deal_id=d.deal_id, type="stage", payload={"from": "contacted", "to": "negotiating"}))
                d.stage = "negotiating"

    action = SHOWN_ACTION.get(r.outcome) or {"counter": "counter", "accept": "agree", "close": "lost"}.get(draft.action, "reply")
    reply.payload = {**(reply.payload or {}), "agent": {"action": action, "reasons": [r.reason],
                                                        **({"failed": r.failed} if r.failed else {})}}
    await _stale_suggestions(db, d)
    name = _name(d, lead)
    key = f"nego:{reply.event_id}"

    if r.outcome == "wait":
        db.add(DealEvent(deal_id=d.deal_id, type="paused", payload={"until": r.resume_on.isoformat(), "reason": r.reason}))
        return {"action": action, "reasons": [r.reason]}
    if r.outcome == "new_contact":
        db.add(AgentProposal(campaign_id=d.campaign_id, deal_id=d.deal_id, key=key, kind="new_contact", status="pending",
                             title=f"Write to {draft.new_contact_email} instead", reason=r.reason,
                             payload={"email": draft.new_contact_email}))
        return {"action": action, "reasons": [r.reason]}
    if r.outcome == "ask_founder":
        q = await ASK.ask(db, d, user_id=user_id, questions=r.questions, creator_text=text, reply_event_id=reply.event_id,
                          name=name, send_mail=send_mail)
        await db.flush()
        reply.payload["agent"]["question_id"] = q.question_id

    price = draft.price
    payload = {"message": draft.message, "source": "ai", "terms": _terms(price), "amounts": _amounts(price),
               "final": False, "strategy": draft.strategy,
               **({"held": HELD_FOR[r.outcome]} if r.outcome in HELD_FOR else {}),
               **({"problems": r.failed} if r.failed else {})}
    if r.outcome == "decide" and draft.action == "accept":
        deal_price = price or draft.their_ask
        if deal_price is None:
            return {"action": action, "reasons": [r.reason]}
        payload.update({"stage": "agreed", "agreed_rate": deal_price.fee or 0, "terms": _terms(deal_price),
                        "deal_type": ("base_plus_commission" if deal_price.commission_pct and deal_price.fee else
                                      "affiliate" if deal_price.commission_pct else "flat"),
                        "commission_pct": deal_price.commission_pct or None})
        kind, title = "agree", f"Agree to {deal_price.words()}"
    elif r.outcome == "decide":
        payload.update({"stage": "lost", "amounts": None, "terms": None})
        kind, title = "mark_lost", "Close politely and mark lost"
    elif not draft.message:
        return {"action": action, "reasons": [r.reason]}
    elif agreed:
        kind, title = "hold_terms", "Reply, keeping the agreed price"
        payload.update({"change": reply.payload.get("change"), "terms": {"fee": d.agreed_rate, "commission_pct": d.commission_pct or 0,
                                                                          "structure": "flat"}})
    elif draft.action == "counter" and price is not None:
        kind, title = "send_counter", f"Offer: {price.words()}"
    else:
        kind, title = "reply", "Reply"
    db.add(AgentProposal(campaign_id=d.campaign_id, deal_id=d.deal_id, key=key, kind=kind, status="pending",
                         title=title, reason=r.reason, payload=payload))
    return {"action": action, "reasons": [r.reason]}


async def compose_follow_up(db: AsyncSession, p: AgentProposal, d: CreatorDeal, *, lead: dict, details: dict, user_id: str,
                            agent=None) -> bool:
    """Writes a follow-up from the whole conversation, the founder's voice and the creator's latest posts (the
    reply agent in follow-up mode). It replaces the code-written fallback only if it passed every check;
    otherwise the plain fallback stays (it's safe, just generic). → True if the AI wrote it."""
    from app.replies import agent as RA

    try:
        async with db.begin_nested():
            ctx = await _context(db, d, lead, details, user_id=user_id, text="", mode="follow_up")
        r = await (agent or RA.reply)(ctx, context=CostContext(user_id=user_id, campaign_id=d.campaign_id))
    except Exception:  # noqa: BLE001
        logger.exception("follow-up writer failed for deal %s", d.deal_id)
        r = None
    pl = dict(p.payload or {})
    if r is not None and r.outcome == "send" and r.draft is not None and r.draft.message and r.draft.price is None:
        pl.update({"message": r.draft.message, "source": "ai", "composed": True})
        p.payload = pl
        return True
    pl.update({"composed": True, "source": pl.get("source", "template")})
    p.payload = pl
    return False


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


async def rerun_after_answer(db: AsyncSession, q) -> None:
    """The founder answered by email: write the creator's reply again with the new fact."""
    from app.models.campaign import Campaign

    if not q.reply_event_id:
        return
    reply = await db.get(DealEvent, q.reply_event_id)
    d = await db.get(CreatorDeal, q.deal_id)
    if reply is None or d is None:
        return
    camp = await db.get(Campaign, d.campaign_id)
    lead = next((l for l in (camp.campaign_leads or []) if isinstance(l, dict) and str(l.get("id")) == d.creator_id), {}) if camp else {}
    await negotiate(db, d, reply, lead=lead, details=(camp.campaign_details if camp else None) or {}, user_id=q.user_id)

"""Deals (spec §8.1, §8.7; roadmap F7.1): the creators a founder is working with in a campaign, from first
contact to paid, with the agreed terms, a negotiation helper and a timeline. Owner only."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.user import get_db_user
from app.billing.costs import CostContext
from app.db.database import get_db
from app.deals import constants as C
from app.deals import negotiation as N
from app.deals.changes import apply_change
from app.models.campaign import Campaign
from app.models.deal import CreatorDeal, DealEvent
from app.models.user import User

router = APIRouter()

def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _campaign(db: AsyncSession, campaign_id: str, user: User):
    row = (await db.execute(
        select(Campaign.campaign_id, Campaign.campaign_leads, Campaign.campaign_details)
        .where(Campaign.campaign_id == campaign_id, Campaign.user_id == user.user_id)
    )).one_or_none()
    if row is None:
        raise HTTPException(404, "Campaign not found")
    return row


async def _deal(db: AsyncSession, deal_id: str, user: User) -> tuple[CreatorDeal, object]:
    row = (await db.execute(
        select(CreatorDeal, Campaign.campaign_leads, Campaign.campaign_details)
        .join(Campaign, Campaign.campaign_id == CreatorDeal.campaign_id)
        .where(CreatorDeal.deal_id == deal_id, Campaign.user_id == user.user_id)
    )).one_or_none()
    if row is None:
        raise HTTPException(404, "Deal not found")
    return row[0], row


def _leads_by_id(leads) -> dict:
    return {l.get("id"): l for l in (leads or []) if isinstance(l, dict)}


def _goal(details) -> Optional[str]:
    return ((details or {}).get("campaign") or {}).get("goal")


def _advice(d: CreatorDeal) -> N.Advice:
    return N.advise(fair_low=d.fair_low, fair_high=d.fair_high, typical_views=d.typical_views,
                    quote=d.agreed_rate if d.stage in C.COMMITTED_STAGES and d.agreed_rate else d.quoted_rate,
                    deliverable=d.deliverable, usage_rights=d.usage_rights, exclusivity_days=d.exclusivity_days or 0)


def _out(d: CreatorDeal, lead: Optional[dict], today: date) -> dict:
    lead = lead or {}
    metrics = lead.get("metrics") or {}
    overdue = bool(d.post_by and d.post_by < today and d.stage in C.POST_DUE_STAGES)
    return {
        "id": d.deal_id, "creator_id": d.creator_id, "platform": d.platform,
        "name": lead.get("title") or d.creator_name or d.creator_id,
        "avatar_url": lead.get("avatar_url"), "url": lead.get("url"), "country": lead.get("country"),
        "deal_status": lead.get("deal_status"), "final_score": lead.get("final_score"),
        "forecast": metrics.get("forecast"),
        "stage": d.stage, "position": d.position,
        "deliverable": d.deliverable, "post_by": d.post_by.isoformat() if d.post_by else None,
        "deal_type": d.deal_type, "commission_pct": d.commission_pct, "usage_rights": d.usage_rights,
        "exclusivity_days": d.exclusivity_days or 0, "disclosure": d.disclosure, "currency": d.currency,
        "quoted_rate": d.quoted_rate, "quoted_commission_pct": d.quoted_commission_pct,
        "agreed_rate": d.agreed_rate, "typical_views": d.typical_views,
        "advice": _advice(d).to_dict(),
        "post_url": d.post_url, "live_at": d.live_at.isoformat() if d.live_at else None,
        "paid_amount": d.paid_amount, "paid_at": d.paid_at.isoformat() if d.paid_at else None,
        "payment_ref": d.payment_ref, "notes": d.notes, "overdue": overdue,
        "contact_email": d.contact_email, "emailing": bool(d.gmail_thread_id),
        "last_read_at": d.last_read_at.isoformat() if d.last_read_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }


async def _proposals(db: AsyncSession, deals: list[CreatorDeal], camp, user: User) -> list[dict]:
    """The campaign's "Needs you" list, brought up to date (spec §7.8)."""
    from app.agent import queue as Q

    leads = _leads_by_id(camp.campaign_leads)
    lead = {d.deal_id: leads.get(d.creator_id) or {} for d in deals}
    names = {i: l.get("title") for i, l in lead.items()}
    pending = await Q.refresh(db, deals, names=names, goal=_goal(camp.campaign_details))
    by_id = {d.deal_id: d for d in deals}
    from app.gmail.service import account_for, usable

    gmail = usable(await account_for(db, user.user_id))
    return [Q.out(p, names.get(p.deal_id) or by_id[p.deal_id].creator_name or "", lead[p.deal_id].get("avatar_url"),
                  can_send=gmail and bool(by_id[p.deal_id].contact_email)) for p in pending]


async def _campaign_proposals(db: AsyncSession, campaign_id: str, camp, user: User) -> list[dict]:
    deals = list((await db.execute(select(CreatorDeal).where(CreatorDeal.campaign_id == campaign_id))).scalars())
    return await _proposals(db, deals, camp, user)


def _summary(deals: list[CreatorDeal], details) -> dict:
    active = [d for d in deals if d.stage != "lost"]
    committed = sum((d.agreed_rate or 0) for d in active if d.stage in C.COMMITTED_STAGES)
    paid = sum((d.paid_amount if d.paid_amount is not None else d.agreed_rate or 0) for d in active if d.stage == "paid")
    budget = ((details or {}).get("campaign") or {}).get("budget_total") or None
    agreed = [d for d in active if d.stage in C.COMMITTED_STAGES]
    return {
        "deals": len(active), "by_stage": {s: sum(1 for d in deals if d.stage == s) for s in C.STAGES},
        "committed": round(committed, 2), "paid": round(paid, 2), "budget": budget,
        "over_budget": bool(budget and committed > float(budget)),
        "live": sum(1 for d in agreed if d.stage in ("live", "paid")), "agreed": len(agreed),
    }


# --- list / create ------------------------------------------------------------------------------

@router.get("/api/campaigns/{campaign_id}/deals")
async def list_deals(campaign_id: str, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    camp = await _campaign(db, campaign_id, user)
    deals = (await db.execute(
        select(CreatorDeal).where(CreatorDeal.campaign_id == campaign_id).order_by(CreatorDeal.position, CreatorDeal.created_at)
    )).scalars().all()
    leads, today = _leads_by_id(camp.campaign_leads), date.today()
    body = {"deals": [_out(d, leads.get(d.creator_id), today) for d in deals], "summary": _summary(list(deals), camp.campaign_details),
            "goal": _goal(camp.campaign_details), "suggested_deal_type": N.suggest_deal_type(_goal(camp.campaign_details))}
    body["proposals"] = await _proposals(db, list(deals), camp, user)
    # the inbox list shows each deal's latest message (who wrote it, a short preview, when)
    last: dict = {}
    unread: dict = {}
    read_at = {d.deal_id: d.last_read_at for d in deals}
    if deals:
        rows = (await db.execute(
            select(DealEvent.deal_id, DealEvent.type, DealEvent.payload, DealEvent.created_at)
            .where(DealEvent.deal_id.in_([d.deal_id for d in deals]), DealEvent.type.in_(("message_sent", "creator_reply")))
            .order_by(DealEvent.created_at)
        )).all()
        for r in rows:
            text = ((r.payload or {}).get("text") or "").strip()
            if text and r.type == "creator_reply" and (read_at[r.deal_id] is None or (r.created_at and r.created_at > read_at[r.deal_id])):
                unread[r.deal_id] = unread.get(r.deal_id, 0) + 1
            if text:
                last[r.deal_id] = {"who": "you" if r.type == "message_sent" else "them", "text": " ".join(text.split())[:120],
                                   "at": r.created_at.isoformat() if r.created_at else None}
    for item in body["deals"]:
        item["last_message"] = last.get(item["id"])
        item["unread"] = unread.get(item["id"], 0)
    return body


@router.post("/api/deals/{deal_id}/read")
async def mark_read(deal_id: str, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """The founder opened the chat: its replies are read."""
    d, _ = await _deal(db, deal_id, user)
    d.last_read_at = _now()
    await db.commit()
    return {"read": deal_id}


@router.get("/api/inbox")
async def inbox(user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """Across all the founder's campaigns: chats with unread replies or a draft waiting (the bell, tab badges and
    browser alerts). Checks Gmail for new replies first (each thread at most every few minutes)."""
    from app.agent import constants as A
    from app.gmail import service as GS
    from app.models.deal import AgentProposal

    camps = {c.campaign_id: c for c in (await db.execute(
        select(Campaign.campaign_id, Campaign.name, Campaign.campaign_leads).where(Campaign.user_id == user.user_id))).all()}
    if not camps:
        return {"items": [], "unread": 0, "waiting": 0, "by_campaign": {}}
    deals = list((await db.execute(select(CreatorDeal).where(CreatorDeal.campaign_id.in_(list(camps))))).scalars())
    account = await GS.account_for(db, user.user_id)
    if GS.usable(account):
        await GS.sync_deals(db, account, deals, user_id=user.user_id)
    if not deals:
        return {"items": [], "unread": 0, "waiting": 0, "by_campaign": {}}
    ids = [d.deal_id for d in deals]
    replies = (await db.execute(select(DealEvent.deal_id, DealEvent.payload, DealEvent.created_at, DealEvent.event_id)
                                .where(DealEvent.deal_id.in_(ids), DealEvent.type == "creator_reply")
                                .order_by(DealEvent.created_at))).all()
    drafts = {p.deal_id for p in (await db.execute(select(AgentProposal.deal_id).where(
        AgentProposal.deal_id.in_(ids), AgentProposal.status == "pending", AgentProposal.kind.in_(A.CHAT_KINDS)))).all()}
    by_deal = {d.deal_id: d for d in deals}
    news: dict = {}
    for r in replies:
        d = by_deal[r.deal_id]
        if d.last_read_at is None or (r.created_at and r.created_at > d.last_read_at):
            n = news.setdefault(r.deal_id, {"count": 0})
            n.update(count=n["count"] + 1, text=" ".join(((r.payload or {}).get("text") or "").split())[:140],
                     at=r.created_at.isoformat() if r.created_at else None, id=r.event_id)
    items = []
    for d in deals:
        if d.deal_id not in news and d.deal_id not in drafts:
            continue
        c = camps[d.campaign_id]
        lead = _leads_by_id(c.campaign_leads).get(d.creator_id) or {}
        n = news.get(d.deal_id) or {}
        items.append({"campaign_id": d.campaign_id, "campaign_name": c.name, "deal_id": d.deal_id,
                      "name": lead.get("title") or d.creator_name, "avatar_url": lead.get("avatar_url"),
                      "unread": n.get("count", 0), "text": n.get("text"), "at": n.get("at"), "event_id": n.get("id"),
                      "draft": d.deal_id in drafts})
    items.sort(key=lambda i: i["at"] or "", reverse=True)
    by_campaign: dict = {}
    for i in items:
        b = by_campaign.setdefault(i["campaign_id"], {"unread": 0, "waiting": 0})
        b["unread"] += i["unread"]
        b["waiting"] += 1
    return {"items": items, "unread": sum(i["unread"] for i in items), "waiting": len(items), "by_campaign": by_campaign}


class NewDeals(BaseModel):
    creator_ids: list[str]


@router.post("/api/campaigns/{campaign_id}/deals")
async def add_deals(campaign_id: str, body: NewDeals, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """Adds creators from this campaign's results; ones already in deals are skipped."""
    camp = await _campaign(db, campaign_id, user)
    leads = _leads_by_id(camp.campaign_leads)
    wanted = [c for c in dict.fromkeys(body.creator_ids) if c in leads]
    if not wanted:
        raise HTTPException(422, "Pick creators from this campaign.")
    existing = set((await db.execute(
        select(CreatorDeal.creator_id).where(CreatorDeal.campaign_id == campaign_id, CreatorDeal.creator_id.in_(wanted))
    )).scalars().all())
    top = (await db.execute(select(func.max(CreatorDeal.position)).where(CreatorDeal.campaign_id == campaign_id))).scalar() or 0
    created = []
    for i, cid in enumerate(c for c in wanted if c not in existing):
        lead = leads[cid]
        d = new_deal(camp, lead, campaign_id, position=top + i + 1)
        db.add(d)
        await db.flush()
        db.add(DealEvent(deal_id=d.deal_id, type="created", payload={"stage": "contacted"}))
        created.append(d)
    await db.commit()
    today = date.today()
    return {"created": [_out(d, leads.get(d.creator_id), today) for d in created], "skipped": len(wanted) - len(created)}


def new_deal(camp, lead: dict, campaign_id: str, *, position: float) -> CreatorDeal:
    """A deal for one of the campaign's creators, prefilled with the usual terms for the campaign's goal."""
    metrics = lead.get("metrics") or {}
    deal_type = N.suggest_deal_type(_goal(camp.campaign_details))
    return CreatorDeal(
        campaign_id=campaign_id, creator_id=lead.get("id"), platform=(lead.get("platform") or "youtube").lower(),
        creator_name=lead.get("title"), stage="contacted", position=position, deal_type=deal_type,
        commission_pct=float(C.SUGGESTED_COMMISSION_PCT) if deal_type == "base_plus_commission" else None,
        deliverable="integration", usage_rights="none", exclusivity_days=0, disclosure=True, currency="USD",
        fair_low=lead.get("fair_low"), fair_high=lead.get("fair_high") or lead.get("valuation") or None,
        typical_views=None if lead.get("data_expired") else metrics.get("avg_views"),
        contact_email=((lead.get("socials") or {}).get("email") or None),
    )


# --- change / delete / timeline -------------------------------------------------------------------

class DealChange(BaseModel):
    stage: Optional[str] = None
    position: Optional[float] = None
    deliverable: Optional[str] = None
    post_by: Optional[date] = None
    deal_type: Optional[str] = None
    commission_pct: Optional[float] = None
    usage_rights: Optional[str] = None
    exclusivity_days: Optional[int] = None
    disclosure: Optional[bool] = None
    quoted_rate: Optional[float] = None
    agreed_rate: Optional[float] = None
    post_url: Optional[str] = None
    paid_amount: Optional[float] = None
    paid_at: Optional[datetime] = None
    payment_ref: Optional[str] = None
    notes: Optional[str] = None
    contact_email: Optional[str] = None
    fair_low: Optional[float] = None  # the founder's own fair range, when ReachAI has none (or they disagree)
    fair_high: Optional[float] = None


_NO_MERGE = object()


async def _merge_quote_edit(db: AsyncSession, d: CreatorDeal, ch: dict):
    """Quote edits a few seconds apart (typing, fixing a typo) become one timeline entry: drops the previous
    entry if it's the latest and recent, and returns the value it started from."""
    if "quoted_rate" not in ch or ch["quoted_rate"] == d.quoted_rate:
        return _NO_MERGE
    last = (await db.execute(select(DealEvent).where(DealEvent.deal_id == d.deal_id)
                             .order_by(DealEvent.created_at.desc()).limit(1))).scalar_one_or_none()
    if not (last and last.type == "quoted_rate" and last.created_at
            and (_now() - last.created_at).total_seconds() < C.QUOTE_EDIT_MERGE_SECONDS):
        return _NO_MERGE
    start = (last.payload or {}).get("from")
    await db.delete(last)
    return start


@router.patch("/api/deals/{deal_id}")
async def change_deal(deal_id: str, body: DealChange, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    d, row = await _deal(db, deal_id, user)
    ch = body.model_dump(exclude_unset=True)
    merged_from = await _merge_quote_edit(db, d, ch)
    apply_change(db, d, ch)
    if merged_from is not _NO_MERGE:
        for obj in list(db.new):
            if isinstance(obj, DealEvent) and obj.type == "quoted_rate":
                if merged_from == ch.get("quoted_rate"):
                    db.expunge(obj)  # edited back to where it started: no entry at all
                else:
                    obj.payload = {**(obj.payload or {}), "from": merged_from}
    await db.commit()
    await db.refresh(d)
    return _out(d, _leads_by_id(row.campaign_leads).get(d.creator_id), date.today())


@router.delete("/api/deals/{deal_id}")
async def remove_deal(deal_id: str, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    d, _ = await _deal(db, deal_id, user)
    await db.delete(d)
    await db.commit()
    return {"deleted": deal_id}


@router.get("/api/deals/{deal_id}/events")
async def deal_events(deal_id: str, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    d, _ = await _deal(db, deal_id, user)
    rows = (await db.execute(select(DealEvent).where(DealEvent.deal_id == d.deal_id).order_by(DealEvent.created_at.desc()))).scalars().all()
    return [{"type": e.type, "payload": e.payload, "at": e.created_at.isoformat() if e.created_at else None} for e in rows]


# --- the "Needs you" queue (spec §7.8, roadmap F6.8) ---------------------------------------------

class ReplyIn(BaseModel):
    text: str  # the creator's reply or their ask in the founder's words: untrusted (screened by Jev, numbers checked)


@router.post("/api/deals/{deal_id}/reply")
async def paste_reply(deal_id: str, body: ReplyIn, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """The creator's reply (pasted) or what they asked for (typed, e.g. "$7 + 20% commission"). The negotiation
    agent reads it and suggests the next step (app/negotiation/)."""
    from app.agent import constants as A
    from app.negotiation.run import negotiate

    text = (body.text or "").strip()[: A.MAX_REPLY_EVENT_CHARS]
    if not text:
        raise HTTPException(422, "Paste their reply or type what they asked for.")
    d, row = await _deal(db, deal_id, user)
    from app.gmail.mail import same_text

    replies = (await db.execute(select(DealEvent.payload).where(DealEvent.deal_id == d.deal_id, DealEvent.type == "creator_reply"))).scalars()
    if any(same_text((p or {}).get("text"), text) for p in replies):
        raise HTTPException(409, "That's already in the chat.")
    reply = DealEvent(deal_id=d.deal_id, type="creator_reply", payload={"text": text, "source": "pasted"})
    db.add(reply)
    await db.flush()
    result = await negotiate(db, d, reply, lead=_leads_by_id(row.campaign_leads).get(d.creator_id) or {},
                             details=row.campaign_details or {}, user_id=user.user_id)
    await db.commit()
    await db.refresh(d)
    return {"agent": result, "deal": _out(d, _leads_by_id(row.campaign_leads).get(d.creator_id), date.today()),
            "proposals": await _campaign_proposals(db, d.campaign_id, row, user)}


@router.post("/api/deals/{deal_id}/negotiate")
async def negotiate_again(deal_id: str, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """Runs the negotiation agent again on their latest message (after you set a fair price or changed terms)."""
    from app.negotiation.run import negotiate

    d, row = await _deal(db, deal_id, user)
    reply = (await db.execute(select(DealEvent).where(DealEvent.deal_id == d.deal_id, DealEvent.type == "creator_reply")
                              .order_by(DealEvent.created_at.desc()).limit(1))).scalar_one_or_none()
    if reply is None:
        raise HTTPException(422, "There's no reply from them yet.")
    lead = _leads_by_id(row.campaign_leads).get(d.creator_id) or {}
    result = await negotiate(db, d, reply, lead=lead, details=row.campaign_details or {}, user_id=user.user_id)
    await db.commit()
    await db.refresh(d)
    return {"agent": result, "deal": _out(d, lead, date.today()), "proposals": await _campaign_proposals(db, d.campaign_id, row, user)}


class MessageIn(BaseModel):
    text: str  # written by the founder
    via: str = "gmail"  # "gmail" sends it when connected and we have their email; "copy" only records it


@router.post("/api/deals/{deal_id}/message")
async def send_own_message(deal_id: str, body: MessageIn, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """The founder's own message in the chat. Sent from their Gmail in the deal's thread when possible, else
    recorded as sent (they copy it). Replaces any pending suggestion: the agent reads it next time."""
    from app.agent import constants as A
    from app.gmail.service import account_for, send_for_deal, usable
    from app.models.deal import AgentProposal

    text = (body.text or "").strip()
    if not text:
        raise HTTPException(422, "Write a message first.")
    if len(text) > 5000:
        raise HTTPException(422, "That message is too long.")
    d, row = await _deal(db, deal_id, user)
    via = None
    if body.via != "copy" and d.contact_email:
        account = await account_for(db, user.user_id)
        if usable(account):
            subject = None if d.gmail_thread_id else f"{(row.campaign_details or {}).get('brand', {}).get('name') or 'Working together'}"
            via = await send_for_deal(db, account, d, text, subject=subject)
    db.add(DealEvent(deal_id=d.deal_id, type="message_sent",
                     payload={"kind": "manual", "text": text, "amounts": None, "edited": False, "via": "gmail" if via else "copied", **(via or {})}))
    for p in (await db.execute(select(AgentProposal).where(AgentProposal.deal_id == d.deal_id, AgentProposal.status == "pending",
                                                           AgentProposal.kind.in_(A.CHAT_KINDS)))).scalars():
        p.status = "stale"
    await db.commit()
    await db.refresh(d)
    return {"sent": bool(via), "deal": _out(d, _leads_by_id(row.campaign_leads).get(d.creator_id), date.today()),
            "proposals": await _campaign_proposals(db, d.campaign_id, row, user)}


async def _proposal(db: AsyncSession, proposal_id: str, user: User):
    from app.models.deal import AgentProposal

    row = (await db.execute(
        select(AgentProposal, CreatorDeal, Campaign.campaign_leads, Campaign.campaign_details)
        .join(CreatorDeal, CreatorDeal.deal_id == AgentProposal.deal_id)
        .join(Campaign, Campaign.campaign_id == CreatorDeal.campaign_id)
        .where(AgentProposal.proposal_id == proposal_id, Campaign.user_id == user.user_id)
    )).one_or_none()
    if row is None:
        raise HTTPException(404, "Suggestion not found")
    if row[0].status != "pending":
        raise HTTPException(409, "This suggestion was already handled.")
    return row


class ApproveIn(BaseModel):
    message: Optional[str] = None  # the founder's edited message, if they changed it
    via: str = "gmail"  # "gmail" sends it when Gmail is connected and we have their email; "copy" only records it


@router.post("/api/proposals/{proposal_id}/approve")
async def approve_proposal(proposal_id: str, body: ApproveIn, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    from app.agent import queue as Q
    MAX_MESSAGE_CHARS = 2700

    row = await _proposal(db, proposal_id, user)
    p, d = row[0], row[1]
    if body.message and len(body.message) > MAX_MESSAGE_CHARS * 3:
        raise HTTPException(422, "That message is too long.")
    send = None
    if body.via != "copy" and d.contact_email:
        from app.gmail.service import account_for, send_for_deal, usable

        account = await account_for(db, user.user_id)
        if usable(account):
            async def send(text: str) -> dict:
                return await send_for_deal(db, account, d, text)
    result = await Q.approve(db, p, d, body.message, send=send)
    await db.commit()
    await db.refresh(d)
    deal = _out(d, _leads_by_id(row.campaign_leads).get(d.creator_id), date.today())
    return {"deal": deal, "sent": bool(result.get("sent")), "proposals": await _campaign_proposals(db, d.campaign_id, row, user)}


@router.post("/api/proposals/{proposal_id}/skip")
async def skip_proposal(proposal_id: str, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    from app.agent import queue as Q

    row = await _proposal(db, proposal_id, user)
    Q.skip(db, row[0])
    await db.commit()
    return {"proposals": await _campaign_proposals(db, row[1].campaign_id, row, user)}


@router.post("/api/proposals/{proposal_id}/accept-change")
async def accept_change(proposal_id: str, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """After agreeing, the creator asked for more and the founder accepts it: the agreed price becomes their ask."""
    from app.deals.changes import validate

    row = await _proposal(db, proposal_id, user)
    p, d = row[0], row[1]
    to = ((p.payload or {}).get("change") or {}).get("to") or {}
    if p.kind != "hold_terms" or to.get("fee") is None:
        raise HTTPException(422, "There's no new price to accept.")
    ch = {"agreed_rate": float(to["fee"])}
    if to.get("commission_pct"):
        ch.update({"commission_pct": float(to["commission_pct"]), "deal_type": "base_plus_commission"})
    validate(d, ch)
    apply_change(db, d, ch)
    db.add(DealEvent(deal_id=d.deal_id, type="proposal", payload={"kind": p.kind, "title": p.title, "decision": "accepted_new_price"}))
    p.status, p.decided_at = "skipped", _now()
    await db.commit()
    await db.refresh(d)
    return {"deal": _out(d, _leads_by_id(row.campaign_leads).get(d.creator_id), date.today()),
            "proposals": await _campaign_proposals(db, d.campaign_id, row, user)}


@router.post("/api/proposals/{proposal_id}/reword")
async def reword_proposal(proposal_id: str, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """Another wording from the agent's writer: same terms, same checks."""
    from app.negotiation.run import reword

    row = await _proposal(db, proposal_id, user)
    p, d = row[0], row[1]
    if not (p.payload or {}).get("message") or not p.key.startswith("nego:"):
        raise HTTPException(422, "This suggestion has no message to reword.")
    text, source = await reword(db, p, d, lead=_leads_by_id(row.campaign_leads).get(d.creator_id) or {},
                                details=row.campaign_details or {}, user_id=user.user_id)
    await db.commit()
    return {"message": text, "source": source}


# --- add a creator you already know (roadmap F1.23) ------------------------------------------------

class ByLink(BaseModel):
    link: str  # their channel link or @handle
    email: Optional[str] = None


@router.post("/api/campaigns/{campaign_id}/creators/by-link")
async def add_creator_by_link(campaign_id: str, body: ByLink, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """Measures the channel like a search would (no Jev, no LLM) and adds it to this campaign's creators."""
    from sqlalchemy import update

    from app.creators.by_link import lead_from_link, parse_youtube
    from app.deals.changes import validate
    from app.platforms.youtube_api import HttpYouTubeAPI, YouTubeAPIError

    camp = await _campaign(db, campaign_id, user)
    if parse_youtube(body.link) == (None, None):
        raise HTTPException(422, "Paste a YouTube channel link, like youtube.com/@name or youtube.com/channel/UC…")
    email = None
    if body.email:
        ch = {"contact_email": body.email}
        validate(CreatorDeal(platform="youtube"), ch)
        email = ch["contact_email"]
    leads = list(camp.campaign_leads or [])
    topics = next((l.get("match_terms") for l in leads if isinstance(l, dict) and l.get("match_terms")), None)
    try:
        api = HttpYouTubeAPI(context=CostContext(user_id=user.user_id, campaign_id=campaign_id))
    except YouTubeAPIError:
        raise HTTPException(503, "YouTube isn't set up on this server.")
    try:
        lead = await lead_from_link(body.link, camp.campaign_details or {}, api=api, email=email, topics=topics)
    finally:
        await api.aclose()
    if lead is None:
        raise HTTPException(404, "Couldn't find that channel on YouTube.")
    existing = next((i for i, l in enumerate(leads) if isinstance(l, dict) and l.get("id") == lead["id"]), None)
    if existing is not None:
        if email:
            leads[existing] = {**leads[existing], "socials": {**(leads[existing].get("socials") or {}), "email": email}}
        lead = leads[existing]
    else:
        leads.append(lead)
    await db.execute(update(Campaign).where(Campaign.campaign_id == campaign_id).values(campaign_leads=leads))
    await db.commit()
    return {"lead": lead, "added": existing is None}

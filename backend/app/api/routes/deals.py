"""Deals (spec §8.1, §8.7; roadmap F7.1): the creators a founder is working with in a campaign, from first
contact to paid, with the agreed terms, a negotiation helper and a timeline. Owner only."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.user import get_db_user
from app.billing.costs import CostContext
from app.db.database import get_db
from app.deals import constants as C
from app.deals import negotiation as N
from app.models.campaign import Campaign
from app.models.deal import CreatorDeal, DealEvent
from app.models.user import User

router = APIRouter()

PLATFORM_HOSTS = {"youtube": ("youtube.com", "youtu.be"), "instagram": ("instagram.com",), "x": ("x.com", "twitter.com"),
                  "linkedin": ("linkedin.com",)}
EDITABLE = ("stage", "deliverable", "post_by", "deal_type", "commission_pct", "usage_rights", "exclusivity_days",
            "disclosure", "quoted_rate", "agreed_rate", "post_url", "paid_amount", "paid_at", "payment_ref", "notes", "position")


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
        "quoted_rate": d.quoted_rate, "agreed_rate": d.agreed_rate, "typical_views": d.typical_views,
        "advice": _advice(d).to_dict(),
        "post_url": d.post_url, "live_at": d.live_at.isoformat() if d.live_at else None,
        "paid_amount": d.paid_amount, "paid_at": d.paid_at.isoformat() if d.paid_at else None,
        "payment_ref": d.payment_ref, "notes": d.notes, "overdue": overdue,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }


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
    return {"deals": [_out(d, leads.get(d.creator_id), today) for d in deals], "summary": _summary(list(deals), camp.campaign_details),
            "goal": _goal(camp.campaign_details), "suggested_deal_type": N.suggest_deal_type(_goal(camp.campaign_details))}


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
    deal_type = N.suggest_deal_type(_goal(camp.campaign_details))
    created = []
    for i, cid in enumerate(c for c in wanted if c not in existing):
        lead = leads[cid]
        metrics = lead.get("metrics") or {}
        d = CreatorDeal(
            campaign_id=campaign_id, creator_id=cid, platform=(lead.get("platform") or "youtube").lower(),
            creator_name=lead.get("title"), stage="contacted", position=top + i + 1, deal_type=deal_type,
            commission_pct=float(C.SUGGESTED_COMMISSION_PCT) if deal_type == "base_plus_commission" else None,
            deliverable="integration", usage_rights="none", exclusivity_days=0, disclosure=True, currency="USD",
            fair_low=lead.get("fair_low"), fair_high=lead.get("fair_high") or lead.get("valuation") or None,
            typical_views=None if lead.get("data_expired") else metrics.get("avg_views"),
        )
        db.add(d)
        await db.flush()
        db.add(DealEvent(deal_id=d.deal_id, type="created", payload={"stage": "contacted"}))
        created.append(d)
    await db.commit()
    today = date.today()
    return {"created": [_out(d, leads.get(d.creator_id), today) for d in created], "skipped": len(wanted) - len(created)}


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


def _validate(d: CreatorDeal, ch: dict) -> None:
    def bad(msg: str):
        raise HTTPException(422, msg)

    if "stage" in ch and ch["stage"] not in C.STAGES:
        bad("Unknown stage.")
    if "deliverable" in ch and ch["deliverable"] not in C.DELIVERABLE_MULTIPLIER:
        bad("Unknown deliverable.")
    if "deal_type" in ch and ch["deal_type"] not in C.DEAL_TYPES:
        bad("Unknown deal type.")
    if "usage_rights" in ch and ch["usage_rights"] not in C.USAGE_UPLIFT:
        bad("Unknown usage rights.")
    for k in ("quoted_rate", "agreed_rate", "paid_amount"):
        if ch.get(k) is not None and not (0 <= ch[k] <= C.MAX_RATE):
            bad("Prices must be between $0 and $10M.")
    if ch.get("commission_pct") is not None and not (0 <= ch["commission_pct"] <= 100):
        bad("Commission must be 0–100%.")
    if ch.get("exclusivity_days") is not None and not (0 <= ch["exclusivity_days"] <= 365):
        bad("Exclusivity must be 0–365 days.")
    if ch.get("notes") and len(ch["notes"]) > C.MAX_NOTES_CHARS:
        bad("Notes are too long.")
    if ch.get("post_url"):
        u = urlparse(ch["post_url"].strip())
        hosts = PLATFORM_HOSTS.get(d.platform, ())
        host = (u.hostname or "").lower()
        if u.scheme not in ("http", "https") or (hosts and not any(host == h or host.endswith("." + h) for h in hosts)):
            bad(f"That doesn't look like a {d.platform.title()} link.")


@router.patch("/api/deals/{deal_id}")
async def change_deal(deal_id: str, body: DealChange, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    d, row = await _deal(db, deal_id, user)
    ch = body.model_dump(exclude_unset=True)
    _validate(d, ch)
    events = []
    if "stage" in ch and ch["stage"] != d.stage:
        events.append(("stage", {"from": d.stage, "to": ch["stage"]}))
        if ch["stage"] == "live" and not d.live_at:
            d.live_at = _now()
        if ch["stage"] == "paid" and not d.paid_at and "paid_at" not in ch:
            d.paid_at = _now()
            if d.paid_amount is None and "paid_amount" not in ch:
                d.paid_amount = d.agreed_rate
    for k in ("quoted_rate", "agreed_rate"):
        if k in ch and ch[k] != getattr(d, k):
            events.append((k, {"from": getattr(d, k), "to": ch[k]}))
    if ch.get("post_url") and ch["post_url"] != d.post_url:
        events.append(("post_url", {"to": ch["post_url"].strip()}))
        ch["post_url"] = ch["post_url"].strip()
    if "paid_at" in ch and ch["paid_at"] and not d.paid_at:
        events.append(("paid", {"amount": ch.get("paid_amount", d.paid_amount or d.agreed_rate)}))
    for k in EDITABLE:
        if k in ch:
            setattr(d, k, ch[k])
    d.updated_at = _now()
    for t, payload in events:
        db.add(DealEvent(deal_id=d.deal_id, type=t, payload=payload))
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


# --- negotiation message --------------------------------------------------------------------------

class CounterIn(BaseModel):
    creator_reply: Optional[str] = None  # pasted by the founder; untrusted, read by Jev only
    rewrite: bool = False  # ask the LLM to reword the template


@router.post("/api/deals/{deal_id}/counter")
async def counter_message(deal_id: str, body: CounterIn, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """The reply to send the creator: numbers and template from code; Jev reads their pasted reply to pick the
    angle; the LLM rewords it on request (checked to keep exactly our numbers)."""
    from app.deals.reply import read_reply, rewrite

    d, row = await _deal(db, deal_id, user)
    lead = _leads_by_id(row.campaign_leads).get(d.creator_id) or {}
    goal = _goal(row.campaign_details)
    advice = N.advise(fair_low=d.fair_low, fair_high=d.fair_high, typical_views=d.typical_views, quote=d.quoted_rate,
                      deliverable=d.deliverable, usage_rights=d.usage_rights, exclusivity_days=d.exclusivity_days or 0)
    if not advice.fair_high:
        raise HTTPException(422, "There's no fair price for this creator, so there's nothing to compare the quote with.")
    ctx = CostContext(user_id=user.user_id, campaign_id=d.campaign_id)
    signals = await read_reply(body.creator_reply, ctx) if (body.creator_reply or "").strip() else {}
    angle = N.angle_for(advice, goal=goal, signals=signals)
    amounts = N.amounts_for(advice, angle, d.quoted_rate)
    name = lead.get("title") or d.creator_name or ""
    post_by = d.post_by.strftime("%B %-d") if d.post_by else None
    text = N.template(name=name, advice=advice, angle=angle, amounts=amounts, deliverable=d.deliverable,
                      usage_rights=d.usage_rights, post_by=post_by, typical_views=d.typical_views)
    source = "template"
    if body.rewrite:
        text, source = await rewrite(name=name, angle=angle, amounts=amounts, deliverable=d.deliverable,
                                     usage_rights=d.usage_rights, exclusivity_days=d.exclusivity_days or 0,
                                     post_by=post_by, typical_views=d.typical_views, goal=goal, fallback=text, context=ctx)
    return {"advice": advice.to_dict(), "angle": angle, "signals": signals, "amounts": amounts, "message": text, "source": source}

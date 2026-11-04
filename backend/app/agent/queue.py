"""The "Needs you" queue (spec §7.8, roadmap F6.8): keeps each deal's suggested next steps in
`agent_proposals`, and carries out the ones the founder approves. Nothing here runs on its own: a suggestion
only changes a deal when the founder approves it, and messages are "sent" by the founder (copied) until
Gmail is connected (F6.5).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import constants as A
from app.agent.proposals import Ev, propose
from app.deals.changes import apply_change
from app.deals.reply import allowed
from app.models.deal import AgentProposal, CreatorDeal, DealEvent


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def refresh(db: AsyncSession, deals: list[CreatorDeal], *, names: dict, goal: Optional[str],
                  today: Optional[date] = None) -> list[AgentProposal]:
    """Brings the stored suggestions in line with the deals (new ones added, outdated ones marked stale; ones
    the founder approved or skipped never come back) and returns the pending ones, oldest first. Commits."""
    if not deals:
        return []
    today = today or date.today()
    ids = [d.deal_id for d in deals]
    events: dict[str, list[Ev]] = {i: [] for i in ids}
    for e in (await db.execute(select(DealEvent).where(DealEvent.deal_id.in_(ids)))).scalars():
        events[e.deal_id].append(Ev(e.event_id, e.type, e.payload or {}, e.created_at or _now()))
    stored: dict[tuple[str, str], AgentProposal] = {
        (p.deal_id, p.key): p for p in (await db.execute(select(AgentProposal).where(AgentProposal.deal_id.in_(ids)))).scalars()
    }
    wanted: set[tuple[str, str]] = set()
    for d in deals:
        for p in propose(d, events[d.deal_id], name=names.get(d.deal_id) or d.creator_name or "", goal=goal, today=today):
            k = (d.deal_id, p.key)
            wanted.add(k)
            have = stored.get(k)
            if have is None:
                await db.execute(pg_insert(AgentProposal).values(
                    campaign_id=d.campaign_id, deal_id=d.deal_id, key=p.key, kind=p.kind, status="pending",
                    title=p.title, reason=p.reason, payload=p.payload,
                ).on_conflict_do_nothing(constraint="uq_agent_proposals_deal_key"))
            elif have.status == "stale":
                have.status, have.title, have.reason, have.payload = "pending", p.title, p.reason, p.payload
    for k, p in stored.items():
        if p.status == "pending" and k not in wanted:
            p.status = "stale"
    await db.commit()
    return list((await db.execute(
        select(AgentProposal).where(AgentProposal.deal_id.in_(ids), AgentProposal.status == "pending")
        .order_by(AgentProposal.created_at)
    )).scalars())


def _change_for(p: AgentProposal, d: CreatorDeal) -> dict:
    pl = p.payload or {}
    early = d.stage == "contacted"
    if p.kind == "record_quote":
        return {"quoted_rate": float(pl["quoted_rate"]), **({"stage": "negotiating"} if early else {})}
    if p.kind == "send_counter":
        return {"stage": "negotiating"} if early else {}
    if p.kind == "agree":
        ch = {"agreed_rate": float(pl["agreed_rate"]), "stage": "agreed"}
        if pl.get("deal_type"):
            ch["deal_type"] = pl["deal_type"]
        if pl.get("commission_pct") is not None:
            ch["commission_pct"] = float(pl["commission_pct"])
        return ch
    if p.kind in ("mark_live", "mark_lost", "mark_paid"):
        return {"stage": pl["stage"]}
    return {}


def approve(db: AsyncSession, p: AgentProposal, d: CreatorDeal, message: Optional[str]) -> None:
    """Carries out an approved suggestion from its stored payload (never from model text). The caller commits."""
    apply_change(db, d, _change_for(p, d))
    pl = p.payload or {}
    result: dict = {}
    if p.kind in A.MESSAGE_KINDS and pl.get("message"):
        final = (message if message and message.strip() else pl["message"]).strip()
        edited = final != pl["message"].strip()
        amounts = pl.get("amounts")
        # an edited message keeps its amounts only if it still says exactly our numbers (used if they accept)
        keep = amounts if amounts and (not edited or allowed(final, amounts)) else None
        db.add(DealEvent(deal_id=d.deal_id, type="message_sent",
                         payload={"kind": p.kind, "text": final, "amounts": keep, "edited": edited, "final": bool(pl.get("final")),
                                  "proposal_id": p.proposal_id}))
        result = {"message": final, "edited": edited}
    db.add(DealEvent(deal_id=d.deal_id, type="proposal", payload={"kind": p.kind, "title": p.title, "decision": "approved",
                                                                 "edited": result.get("edited", False)}))
    p.status, p.decided_at, p.result = "approved", _now(), result


def skip(db: AsyncSession, p: AgentProposal) -> None:
    db.add(DealEvent(deal_id=p.deal_id, type="proposal", payload={"kind": p.kind, "title": p.title, "decision": "skipped"}))
    p.status, p.decided_at = "skipped", _now()


def out(p: AgentProposal, name: str, avatar: Optional[str]) -> dict:
    pl = p.payload or {}
    return {"id": p.proposal_id, "deal_id": p.deal_id, "kind": p.kind, "title": p.title, "reason": p.reason,
            "message": pl.get("message"), "source": pl.get("source", "template"),
            "can_reword": p.kind in ("send_counter", "agree") and bool(pl.get("message") and pl.get("angle")),
            "is_message": p.kind in A.MESSAGE_KINDS and bool(pl.get("message")),
            "name": name, "avatar_url": avatar, "created_at": p.created_at.isoformat() if p.created_at else None}

"""Autopilot (decided Nov 14, roadmap F6.8d/F6.7): once the founder starts outreach, ReachAI sends the messages
itself, from the founder's Gmail, one at a time, and stops for the founder at real decisions.

- Sent automatically (AUTO_KINDS): first emails (unless the founder chose to check them first), follow-ups,
  late-post nudges, the negotiation agent's counter-offers and replies that keep agreed terms, and the
  confirmation after the founder agrees. Counters are always inside the founder's limits: the numbers come from
  code (app/negotiation/decide.py) and the text is checked to say exactly those numbers.
- Never automatic (DECISION_KINDS): agreeing a price, and closing a deal. The founder gets a notification.
- Held for the founder, with the reason shown in the chat (HELD): a draft that failed its checks, an address
  contacted recently in another campaign, no email, a question only the founder can answer, payment/contract
  terms, or a send that failed twice.
- Pacing that keeps the founder's inbox out of spam: replies ~10 minutes after the creator writes; new
  conversations 2–6 minutes apart, in the creator's daytime; Gmail's daily cap (40) still applies.
- Only messages drafted after autopilot was switched on are sent (older drafts stay for the founder).

`send_next` does one step and says how long to wait before the next; the Inngest function loops on it with
durable sleeps (app/inngest/functions.py)."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.agent import constants as A

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(t: Optional[datetime]) -> Optional[datetime]:
    return t.replace(tzinfo=timezone.utc) if t is not None and t.tzinfo is None else t


@dataclass
class Settings:
    autopilot: bool = False
    review_first: bool = False
    since: Optional[datetime] = None


def settings_of(raw: Optional[dict]) -> Settings:
    raw = raw or {}
    since = None
    if raw.get("since"):
        try:
            since = _aware(datetime.fromisoformat(raw["since"]))
        except ValueError:
            since = None
    return Settings(bool(raw.get("autopilot")), bool(raw.get("review_first")), since)


def turned_on(raw: Optional[dict], *, autopilot: bool, review_first: bool, now: Optional[datetime] = None) -> dict:
    """New settings. Switching autopilot on (again) moves `since` to now: drafts written before stay manual."""
    old = settings_of(raw)
    since = old.since if (old.autopilot and autopilot and old.since) else (now or _now())
    return {"autopilot": autopilot, "review_first": review_first, "since": since.isoformat()}


def hold_reason(p, d, lead: Optional[dict], s: Settings, *, email_route: bool) -> Optional[str]:
    """Why this suggestion can't go out by itself: a HELD key (the founder is told), "manual" (not autopilot's
    to send: a decision, or drafted before autopilot was on), or None (it can be sent)."""
    pl = p.payload or {}
    if not s.autopilot or p.kind not in A.AUTO_KINDS or not pl.get("message"):
        return "manual"
    created = _aware(p.created_at)
    if s.since and created and created < s.since:
        return "manual"
    if pl.get("auto_failures", 0) >= A.MAX_AUTO_FAILURES:
        return "failed"
    if p.kind == "pitch":
        if s.review_first:
            return "review_first"
        if pl.get("needs_review"):
            return "needs_review"
        if ((lead or {}).get("contact") or {}).get("contacted_before"):
            return "contacted_before"
    if pl.get("held") in ("question", "needs_human"):
        return pl["held"]
    if not email_route:
        return "no_email"
    return None


def _gap(p) -> timedelta:
    """A stable random-looking gap per message (2–6 minutes), so new conversations don't go out like a robot."""
    lo, hi = A.FIRST_EMAIL_GAP_MINUTES
    frac = int(hashlib.sha256(str(p.proposal_id).encode()).hexdigest()[:4], 16) / 0xFFFF
    return timedelta(minutes=lo + (hi - lo) * frac)


def daytime(at: datetime, country: Optional[str]) -> datetime:
    """`at`, or the next moment inside SEND_HOURS in the creator's country (unknown country: `at`)."""
    tz = A.COUNTRY_TZ.get((country or "").upper())
    if not tz:
        return at
    local = at.astimezone(ZoneInfo(tz))
    start, end = A.SEND_HOURS
    if start <= local.hour < end:
        return at
    day = local.date() if local.hour < start else local.date() + timedelta(days=1)
    return datetime.combine(day, time(start), tzinfo=ZoneInfo(tz)).astimezone(timezone.utc)


def due_at(p, lead: Optional[dict], *, now: datetime, last_first: Optional[datetime]) -> datetime:
    created = _aware(p.created_at) or now
    if p.kind == "pitch":
        at = max(created, (last_first + _gap(p)) if last_first else created)
        return daytime(at, (lead or {}).get("country"))
    if p.kind in ("send_counter", "hold_terms"):
        return created + timedelta(minutes=A.REPLY_DELAY_MINUTES)
    return created


async def _campaigns(db: AsyncSession, user_id: str) -> list:
    from app.models.campaign import Campaign

    rows = (await db.execute(select(Campaign).where(Campaign.user_id == user_id,
                                                    Campaign.outreach_settings.is_not(None)))).scalars().all()
    return [c for c in rows if settings_of(c.outreach_settings).autopilot]


async def _last_first_email(db: AsyncSession, deal_ids: list[str]) -> Optional[datetime]:
    from app.models.deal import DealEvent

    if not deal_ids:
        return None
    rows = (await db.execute(select(DealEvent.created_at, DealEvent.payload).where(
        DealEvent.deal_id.in_(deal_ids), DealEvent.type == "message_sent")
        .order_by(DealEvent.created_at.desc()).limit(200))).all()
    for at, payload in rows:
        if (payload or {}).get("kind") == "pitch" and (payload or {}).get("via") == "gmail":
            return _aware(at)
    return None


def _note(p, key: Optional[str]) -> None:
    """Records on the suggestion why autopilot is holding it (or that it no longer is)."""
    pl = dict(p.payload or {})
    if pl.get("held") == key:
        return
    if key:
        pl["held"] = key
    else:
        pl.pop("held", None)
    p.payload = pl
    flag_modified(p, "payload")


async def send_next(db: AsyncSession, user_id: str, *, now: Optional[datetime] = None, send=None) -> dict:
    """Sends the next message that's due across the founder's autopilot campaigns, if any.
    → {"sent": kind | None, "wait": seconds until the next is due | None (nothing due soon: stop)}.
    `send(db, account, deal, text, subject)` defaults to the Gmail sender (tests pass a fake)."""
    from app.agent import queue as Q
    from app.gmail import service as GS
    from app.models.deal import AgentProposal, CreatorDeal
    from app.outreach.drafts import auto_channel

    now = now or _now()
    send = send or GS.send_for_deal
    account = await GS.account_for(db, user_id)
    if not GS.usable(account):
        return {"sent": None, "wait": None, "why": "gmail"}
    camps = await _campaigns(db, user_id)
    if not camps:
        return {"sent": None, "wait": None, "why": "off"}

    candidates = []  # (due, proposal, deal, campaign, lead)
    all_ids: list[str] = []
    for c in camps:
        s = settings_of(c.outreach_settings)
        leads = {str(l.get("id")): l for l in c.campaign_leads or [] if isinstance(l, dict)}
        deals = list((await db.execute(select(CreatorDeal).where(CreatorDeal.campaign_id == c.campaign_id))).scalars())
        if not deals:
            continue
        all_ids += [d.deal_id for d in deals]
        goal = (((c.campaign_details or {}).get("campaign") or {}).get("goal"))
        # brings the time-based suggestions (follow-ups, late-post nudges) up to date, like opening the tab does
        pending = await Q.refresh(db, deals, names={d.deal_id: (leads.get(d.creator_id) or {}).get("title") for d in deals}, goal=goal)
        by_id = {d.deal_id: d for d in deals}
        for p in pending:
            d = by_id.get(p.deal_id)
            if d is None:
                continue
            lead = leads.get(d.creator_id)
            route = bool(d.contact_email) and auto_channel(d, lead) == "email"
            why = hold_reason(p, d, lead, s, email_route=route)
            if why == "manual":
                continue
            _note(p, why)
            if why is None:
                candidates.append((p, d, c, lead))
    await db.commit()
    if not candidates:
        return {"sent": None, "wait": None, "why": "nothing"}

    last_first = await _last_first_email(db, all_ids)
    timed = sorted(((due_at(p, lead, now=now, last_first=last_first), i, p, d, c)
                    for i, (p, d, c, lead) in enumerate(candidates)), key=lambda t: (t[0], t[1]))
    due, _, p, d, c = timed[0]
    if due > now:
        wait = (due - now).total_seconds()
        return {"sent": None, "wait": wait if wait <= A.MAX_SLEEP_MINUTES * 60 else None, "why": "later"}

    pid, kind = p.proposal_id, p.kind
    subject = None if d.gmail_thread_id else ((p.payload or {}).get("subject")
                                              or ((c.campaign_details or {}).get("brand") or {}).get("name") or "Working together")
    if not await Q.claim(db, p):
        return {"sent": None, "wait": 1, "why": "taken"}  # the founder sent it from the chat meanwhile

    async def do_send(text: str) -> dict:
        return await send(db, account, d, text, subject=subject)

    try:
        await Q.approve(db, p, d, None, send=do_send, subject=subject, auto=True)
        await db.commit()
    except Exception as e:  # noqa: BLE001 - one failure never stops autopilot or loses the message
        await db.rollback()
        await Q.release(db, pid)
        row = await db.get(AgentProposal, pid)
        if isinstance(e, HTTPException) and e.status_code == 429:
            return {"sent": None, "wait": None, "why": "daily_cap"}  # Gmail's daily cap: tomorrow's runs carry on
        if row is not None:
            row.payload = {**(row.payload or {}), "auto_failures": (row.payload or {}).get("auto_failures", 0) + 1}
            await db.commit()
        logger.warning("autopilot send failed (%s): %s", kind, type(e).__name__)
        account = await GS.account_for(db, user_id)
        return {"sent": None, "wait": 30 if GS.usable(account) else None, "why": "failed"}
    return {"sent": kind, "wait": 2, "why": "sent"}


# --- telling the founder ------------------------------------------------------------------------------------

def notice(kind: str, name: str, payload: dict) -> Optional[str]:
    """One line for the founder about a decision or a held message, or None."""
    if kind == "agree":
        terms = payload.get("terms") or {}
        fee = terms.get("fee")
        pct = terms.get("commission_pct")
        price = f"${fee:,.0f}" if fee else ""
        price += f"{' + ' if price else ''}{pct:g}% commission" if pct else ""
        return f"{name} accepted{f' {price}' if price else ''}. Agree to lock it in."
    if kind == "mark_lost":
        if payload.get("bounced"):
            return f"{name}'s email address bounced. Reach them by DM or add another address."
        if payload.get("opt_out"):
            return f"{name} asked not to be contacted again. ReachAI won't email them."
        return f"{name} turned it down. Close it or reply yourself."
    held = payload.get("held")
    if held and held in A.HELD and held != "review_first":
        return f"{name}: {A.HELD[held]}"
    return None


async def notify(db: AsyncSession, user_id: str, *, send_mail=None) -> int:
    """Emails the founder (to their own address, from their own Gmail) about new decisions and held messages in
    autopilot campaigns, once each. The bell in the app shows them too. → how many were new."""
    from app.gmail import client as GC
    from app.gmail import mail
    from app.gmail import service as GS
    from app.mcp.config import app_url
    from app.models.deal import AgentProposal, CreatorDeal

    account = await GS.account_for(db, user_id)
    camps = await _campaigns(db, user_id)
    if not camps:
        return 0
    names = {}
    for c in camps:
        for l in c.campaign_leads or []:
            if isinstance(l, dict):
                names[(c.campaign_id, str(l.get("id")))] = l.get("title")
    rows = (await db.execute(select(AgentProposal, CreatorDeal).join(CreatorDeal, CreatorDeal.deal_id == AgentProposal.deal_id)
                             .where(AgentProposal.campaign_id.in_([c.campaign_id for c in camps]),
                                    AgentProposal.status == "pending"))).all()
    lines: dict[str, list[str]] = {}
    for p, d in rows:
        pl = p.payload or {}
        if pl.get("notified"):
            continue
        line = notice(p.kind, names.get((d.campaign_id, d.creator_id)) or d.creator_name or "A creator", pl)
        if not line:
            continue
        lines.setdefault(d.campaign_id, []).append(line)
        p.payload = {**pl, "notified": True}
    # replies the agent couldn't handle (no fair price, budget used up, AI down, odd message): the founder reads them
    from app.models.deal import DealEvent

    since = _now() - timedelta(days=7)
    replies = (await db.execute(select(DealEvent, CreatorDeal).join(CreatorDeal, CreatorDeal.deal_id == DealEvent.deal_id)
                                .where(CreatorDeal.campaign_id.in_([c.campaign_id for c in camps]),
                                       DealEvent.type == "creator_reply", DealEvent.created_at >= since))).all()
    for e, d in replies:
        pl = e.payload or {}
        agent = pl.get("agent") or {}
        if pl.get("notified") or agent.get("action") != "none":
            continue
        name = names.get((d.campaign_id, d.creator_id)) or d.creator_name or "A creator"
        lines.setdefault(d.campaign_id, []).append(f"{name} replied: {(agent.get('reasons') or ['read it yourself'])[0]}")
        e.payload = {**pl, "notified": True}
    total = sum(len(v) for v in lines.values())
    if not total:
        return 0
    if GS.usable(account):
        base = app_url()
        blocks = []
        for cid, ls in lines.items():
            blocks.append("\n".join(f"- {x}" for x in ls) + f"\nOpen: {base}/campaign/{cid}/outreach")
        body = "\n\n".join(blocks)
        subject = f"ReachAI: {total} creator{'s' if total != 1 else ''} need{'s' if total == 1 else ''} you"
        try:
            if send_mail:
                await send_mail(account.email, subject, body)
            else:
                token = await GS.token_for(account)
                raw = mail.build(sender=account.email, sender_name="ReachAI", to=account.email, subject=subject,
                                 body=body + "\n\nAutopilot keeps sending everything else. Turn it off in Outreach any time.")
                await GC.send(token, raw)
        except Exception as e:  # noqa: BLE001 - the bell still shows them
            logger.warning("autopilot notice email failed: %s", type(e).__name__)
    await db.commit()
    return total

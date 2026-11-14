"""Gmail for deals (spec §7.5): send an approved message in the deal's thread, and pull the creator's new
replies into the deal (Jev reads each one once). Replies are untrusted text (rule 7): stored in their own
event field, read only by Jev, never shown to an LLM."""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.gmail import client as GC
from app.gmail import constants as G
from app.gmail import crypto, mail
from app.models.deal import ConnectedAccount, CreatorDeal, DealEvent

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def account_for(db: AsyncSession, user_id: str) -> Optional[ConnectedAccount]:
    return (await db.execute(select(ConnectedAccount).where(ConnectedAccount.user_id == user_id,
                                                            ConnectedAccount.provider == "gmail"))).scalar_one_or_none()


async def token_for(account: ConnectedAccount) -> str:
    refresh = crypto.decrypt(account.refresh_token)
    if not refresh:
        account.status = "reconnect"
        raise GC.GmailError("Connect Gmail again.", revoked=True)
    try:
        return await GC.access_token(refresh)
    except GC.GmailError as e:
        if e.revoked:
            account.status = "reconnect"
        raise


def usable(account: Optional[ConnectedAccount]) -> bool:
    return bool(account and account.status == "active")


async def send_for_deal(db: AsyncSession, account: ConnectedAccount, d: CreatorDeal, body: str,
                        subject: Optional[str] = None) -> dict:
    """Sends `body` to the deal's contact, as a reply in its thread when there is one, else as a new email
    with `subject`. Updates the deal's thread fields. → {"gmail_id", "thread_id"}. Raises HTTPException."""
    if not d.contact_email:
        raise HTTPException(422, "Add their email address first.")
    from app.contacts.ledger import record_contact, suppressed

    if await suppressed(db, d.contact_email):
        raise HTTPException(422, "This address can't be emailed: the person opted out or it bounced before.")
    today = date.today()
    if account.sent_day != today:
        account.sent_day, account.sent_today = today, 0
    if account.sent_today >= G.DAILY_SEND_CAP:
        raise HTTPException(429, f"You've sent {G.DAILY_SEND_CAP} emails today, the daily limit that keeps your inbox out of spam. Try tomorrow.")
    new_thread = not d.gmail_thread_id
    subj = (subject or "").strip() if new_thread else mail.reply_subject(d.gmail_subject)
    if new_thread and not subj:
        raise HTTPException(422, "Add a subject line.")
    try:
        token = await token_for(account)
        if not account.display_name:  # accounts connected before the name was saved
            account.display_name = await GC.display_name(token)
        # a real sender name ("Srijan Patel <…>") instead of a bare address helps keep first emails out of spam
        raw = mail.build(sender=account.email, sender_name=account.display_name, to=d.contact_email, subject=subj,
                         body=body, in_reply_to=None if new_thread else d.gmail_last_message_id)
        sent = await GC.send(token, raw, None if new_thread else d.gmail_thread_id)
        meta = await GC.message(token, sent["id"])
    except GC.GmailError as e:
        raise HTTPException(409 if e.revoked else 502, str(e))
    account.sent_today += 1
    await record_contact(db, account.user_id, d.contact_email, d.campaign_id)
    d.gmail_thread_id = sent.get("threadId") or d.gmail_thread_id
    if new_thread:
        d.gmail_subject = subj
    d.gmail_last_message_id = mail.header(meta, "Message-ID") or d.gmail_last_message_id
    d.gmail_synced_at = _now()
    return {"gmail_id": sent["id"], "thread_id": d.gmail_thread_id}


async def sync_deal(db: AsyncSession, account: ConnectedAccount, d: CreatorDeal, token: str, *, user_id: str) -> int:
    """Pulls the creator's new messages in the deal's thread into the deal, then runs the negotiation agent on
    the latest one (it suggests the next step). Returns how many new messages."""
    from app.models.campaign import Campaign
    from app.negotiation.run import negotiate

    if not d.gmail_thread_id:
        return 0
    t = await GC.thread(token, d.gmail_thread_id)
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        # opening Deals and the background check can sync the same thread at once: one at a time per deal,
        # so each email is saved once (a unique index backs this up)
        await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"gmail-sync:{d.deal_id}"})
    events = (await db.execute(select(DealEvent).where(DealEvent.deal_id == d.deal_id))).scalars().all()
    seen = {(e.payload or {}).get("gmail_id") for e in events if e.type in ("creator_reply", "message_sent")}
    pasted = [e for e in events if e.type == "creator_reply" and (e.payload or {}).get("source") == "pasted"
              and not (e.payload or {}).get("gmail_id")]
    me = account.email.lower()
    latest = None
    for m in t.get("messages") or []:
        mid = mail.header(m, "Message-ID")
        if mid:
            d.gmail_last_message_id = mid  # our next reply answers the latest message, whoever sent it
        if m.get("id") in seen or mail.sender_email(m) == me or "SENT" in (m.get("labelIds") or []):
            continue
        if mail.is_bounce(m):
            # their address doesn't exist (or their inbox refused us): never email it again, stop the follow-ups
            await _bounced(db, d, m.get("id"), user_id)
            seen.add(m.get("id"))
            continue
        body = mail.reply_text(m)
        if not body:
            continue
        twin = next((e for e in pasted if mail.same_text((e.payload or {}).get("text"), body)), None)
        if twin is not None:  # the founder already pasted this email: link it instead of adding it again
            twin.payload = {**(twin.payload or {}), "gmail_id": m.get("id")}
            pasted.remove(twin)
            continue
        latest = DealEvent(deal_id=d.deal_id, type="creator_reply", payload={"text": body, "gmail_id": m.get("id"), "source": "gmail"})
        db.add(latest)
    d.gmail_synced_at = _now()
    if latest is None:
        return 0
    await db.flush()
    camp = (await db.execute(select(Campaign.campaign_leads, Campaign.campaign_details)
                             .where(Campaign.campaign_id == d.campaign_id))).one()
    lead = next((l for l in (camp.campaign_leads or []) if isinstance(l, dict) and l.get("id") == d.creator_id), {})
    await negotiate(db, d, latest, lead=lead, details=camp.campaign_details or {}, user_id=user_id)
    return 1


async def _bounced(db: AsyncSession, d: CreatorDeal, gmail_id: Optional[str], user_id: str) -> None:
    from app.contacts.ledger import record_contact, suppress
    from app.models.deal import AgentProposal

    if d.contact_email:
        await suppress(db, d.contact_email, "bounce")
        await record_contact(db, user_id, d.contact_email, d.campaign_id, outcome="bounced")
    for p in (await db.execute(select(AgentProposal).where(AgentProposal.deal_id == d.deal_id,
                                                           AgentProposal.status == "pending"))).scalars():
        p.status = "stale"
    db.add(DealEvent(deal_id=d.deal_id, type="bounced", payload={"gmail_id": gmail_id, "address": d.contact_email}))
    db.add(AgentProposal(campaign_id=d.campaign_id, deal_id=d.deal_id, key=f"bounce:{gmail_id}", kind="mark_lost",
                         status="pending", title="Mark lost",
                         reason="Their email address bounced. Reach them by DM, or add a different address in Details.",
                         payload={"stage": "lost", "bounced": True}))


async def sync_deals(db: AsyncSession, account: ConnectedAccount, deals: list[CreatorDeal], *, user_id: str,
                     force: bool = False, budget_seconds: Optional[float] = None) -> int:
    """Checks the threads that are due (not checked in the last few minutes), commits. Returns new replies.
    `budget_seconds`: stop starting new threads after this long (the bell's poll); the rest stay due and are
    checked next time, oldest-checked first so none starves."""
    if not usable(account):
        return 0
    cutoff = _now() - timedelta(minutes=G.SYNC_EVERY_MINUTES)
    due = sorted((d for d in deals if d.gmail_thread_id and d.stage not in ("paid", "lost")
                  and (force or not d.gmail_synced_at or d.gmail_synced_at < cutoff)),
                 key=lambda d: d.gmail_synced_at or datetime.min.replace(tzinfo=timezone.utc))[: G.MAX_THREADS_PER_SYNC]
    if not due:
        return 0
    new = 0
    try:
        token = await token_for(account)
        started = time.monotonic()
        for d in due:
            if budget_seconds is not None and time.monotonic() - started > budget_seconds:
                break
            try:
                new += await sync_deal(db, account, d, token, user_id=user_id)
            except GC.GmailError as e:
                if e.revoked:
                    raise
                logger.warning("gmail sync failed for one thread: %s", type(e).__name__)
            except Exception:  # noqa: BLE001 - one odd thread must not stop the others or lose their replies
                logger.exception("gmail sync failed for deal %s", d.deal_id)
    except GC.GmailError:
        pass  # account marked "reconnect"; the UI asks the founder to connect again
    await db.commit()
    return new

"""Gmail for deals (spec §7.5): send an approved message in the deal's thread, and pull the creator's new
replies into the deal (Jev reads each one once). Replies are untrusted text (rule 7): stored in their own
event field, read only by Jev, never shown to an LLM."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
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
        raw = mail.build(sender=account.email, to=d.contact_email, subject=subj, body=body,
                         in_reply_to=None if new_thread else d.gmail_last_message_id)
        sent = await GC.send(token, raw, None if new_thread else d.gmail_thread_id)
        meta = await GC.message(token, sent["id"])
    except GC.GmailError as e:
        raise HTTPException(409 if e.revoked else 502, str(e))
    account.sent_today += 1
    d.gmail_thread_id = sent.get("threadId") or d.gmail_thread_id
    if new_thread:
        d.gmail_subject = subj
    d.gmail_last_message_id = mail.header(meta, "Message-ID") or d.gmail_last_message_id
    d.gmail_synced_at = _now()
    return {"gmail_id": sent["id"], "thread_id": d.gmail_thread_id}


async def sync_deal(db: AsyncSession, account: ConnectedAccount, d: CreatorDeal, token: str, *, user_id: str) -> int:
    """Pulls new messages from the creator in the deal's thread → creator_reply events. Returns how many."""
    from app.billing.costs import CostContext
    from app.agent.proposals import money_in
    from app.deals.reply import read_reply
    from app.deals.thread import thread_context

    if not d.gmail_thread_id:
        return 0
    t = await GC.thread(token, d.gmail_thread_id)
    events = (await db.execute(select(DealEvent).where(DealEvent.deal_id == d.deal_id))).scalars().all()
    seen = {(e.payload or {}).get("gmail_id") for e in events if e.type in ("creator_reply", "message_sent")}
    me = account.email.lower()
    new = 0
    for m in t.get("messages") or []:
        mid = mail.header(m, "Message-ID")
        if mid:
            d.gmail_last_message_id = mid  # our next reply answers the latest message, whoever sent it
        if m.get("id") in seen or mail.sender_email(m) == me or "SENT" in (m.get("labelIds") or []):
            continue
        text = mail.reply_text(m)
        if not text:
            continue
        signals = await read_reply(text, CostContext(user_id=user_id, campaign_id=d.campaign_id),
                                   thread_context(events, d.quoted_rate))
        db.add(DealEvent(deal_id=d.deal_id, type="creator_reply",
                         payload={"text": text, "signals": signals, "amounts": money_in(text), "gmail_id": m.get("id"), "source": "gmail"}))
        new += 1
    d.gmail_synced_at = _now()
    return new


async def sync_deals(db: AsyncSession, account: ConnectedAccount, deals: list[CreatorDeal], *, user_id: str,
                     force: bool = False) -> int:
    """Checks the threads that are due (not checked in the last few minutes), commits. Returns new replies."""
    if not usable(account):
        return 0
    cutoff = _now() - timedelta(minutes=G.SYNC_EVERY_MINUTES)
    due = [d for d in deals if d.gmail_thread_id and d.stage not in ("paid", "lost")
           and (force or not d.gmail_synced_at or d.gmail_synced_at < cutoff)][: G.MAX_THREADS_PER_SYNC]
    if not due:
        return 0
    new = 0
    try:
        token = await token_for(account)
        for d in due:
            try:
                new += await sync_deal(db, account, d, token, user_id=user_id)
            except GC.GmailError as e:
                if e.revoked:
                    raise
                logger.warning("gmail sync failed for one thread: %s", type(e).__name__)
    except GC.GmailError:
        pass  # account marked "reconnect"; the UI asks the founder to connect again
    await db.commit()
    return new

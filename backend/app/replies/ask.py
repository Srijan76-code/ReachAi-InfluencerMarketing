"""Asking the founder (spec §8.6c): when a creator asks something ReachAI doesn't know, it never guesses. It asks
the founder: one email to their own address (from their own Gmail) and the same question in the chat. Their
answer, from either place, becomes a remembered fact, and the reply is written again with it."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_memory import FounderQuestion

logger = logging.getLogger(__name__)
MAX_ANSWER_CHARS = 2000
QUOTE_CHARS = 600


def _now() -> datetime:
    return datetime.now(timezone.utc)


def email_body(name: str, questions: list[str], creator_text: str, link: str) -> str:
    qs = "\n".join(f"- {q}" for q in questions)
    quote = " ".join((creator_text or "").split())[:QUOTE_CHARS]
    return (f"{name} asked something ReachAI doesn't know, so it hasn't replied yet:\n\n{qs}\n\n"
            f"Their message:\n> {quote}\n\n"
            "Reply to this email with your answer (plain words are fine), or answer in the app:\n"
            f"{link}\n\nReachAI remembers your answer for other creators too, and writes the reply with it.")


async def open_question(db: AsyncSession, deal_id: str) -> Optional[FounderQuestion]:
    return (await db.execute(select(FounderQuestion).where(FounderQuestion.deal_id == deal_id, FounderQuestion.status == "open")
                             .order_by(FounderQuestion.created_at.desc()).limit(1))).scalar_one_or_none()


async def ask(db: AsyncSession, d, *, user_id: str, questions: list[str], creator_text: str, reply_event_id: Optional[str],
              name: str, send_mail=None) -> FounderQuestion:
    """Records the question (replacing an older open one for this deal) and emails the founder. The email failing
    never loses the question: it's in the chat either way. `send_mail(subject, body)` → Gmail thread id (tests)."""
    old = await open_question(db, d.deal_id)
    if old:
        old.status = "dropped"
    q = FounderQuestion(deal_id=d.deal_id, user_id=user_id, reply_event_id=reply_event_id, questions=questions,
                        creator_text=(creator_text or "")[:3000], status="open")
    db.add(q)
    from app.mcp.config import app_url

    subject = f"ReachAI question: {name} asked something only you can answer"
    body = email_body(name, questions, creator_text, f"{app_url()}/campaign/{d.campaign_id}/outreach")
    try:
        q.gmail_thread_id = await (send_mail or _send_to_self)(db, user_id, subject, body)
    except Exception as exc:  # noqa: BLE001 - the chat still shows it
        logger.warning("founder question email failed: %s", type(exc).__name__)
    return q


async def _send_to_self(db: AsyncSession, user_id: str, subject: str, body: str) -> Optional[str]:
    from app.gmail import client as GC
    from app.gmail import mail
    from app.gmail import service as GS

    account = await GS.account_for(db, user_id)
    if not GS.usable(account):
        return None
    token = await GS.token_for(account)
    raw = mail.build(sender=account.email, sender_name="ReachAI", to=account.email, subject=subject, body=body)
    return (await GC.send(token, raw)).get("threadId")


async def answer(db: AsyncSession, q: FounderQuestion, text: str, *, campaign_id: Optional[str]) -> None:
    """Saves the founder's answer and remembers it as a fact (for this campaign). The caller re-runs the agent."""
    from app.replies.memory import remember_fact

    text = (text or "").strip()[:MAX_ANSWER_CHARS]
    q.answer, q.status, q.answered_at = text, "answered", _now()
    await remember_fact(db, q.user_id, " / ".join(q.questions or []), text, campaign_id)


def founder_reply(thread: dict) -> Optional[str]:
    """The founder's answer in the question's email thread: the newest message after our question."""
    from app.gmail import mail

    msgs = (thread or {}).get("messages") or []
    if len(msgs) < 2:
        return None
    text = mail.reply_text(msgs[-1])
    return text.strip() or None if text else None


async def sync_answers(db: AsyncSession, account, user_id: str, *, rerun=None) -> int:
    """Reads the founder's email answers to open questions (run with the Gmail sync). → how many were answered.
    `rerun(db, q)` writes the creator's reply again with the new fact."""
    from app.gmail import client as GC
    from app.gmail import service as GS
    from app.models.deal import CreatorDeal

    rows = (await db.execute(select(FounderQuestion).where(FounderQuestion.user_id == user_id, FounderQuestion.status == "open",
                                                           FounderQuestion.gmail_thread_id.is_not(None)))).scalars().all()
    if not rows:
        return 0
    token = await GS.token_for(account)
    n = 0
    for q in rows:
        try:
            text = founder_reply(await GC.thread(token, q.gmail_thread_id))
        except Exception as exc:  # noqa: BLE001 - one thread never stops the others
            logger.warning("founder answer read failed: %s", type(exc).__name__)
            continue
        if not text:
            continue
        d = await db.get(CreatorDeal, q.deal_id)
        await answer(db, q, text, campaign_id=d.campaign_id if d else None)
        n += 1
        if rerun and d:
            await rerun(db, q)
    await db.commit()
    return n

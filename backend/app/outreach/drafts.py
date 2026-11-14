"""First messages as drafts in each creator's chat (roadmap F7.10c): when a pitch run finishes, every creator
gets an agent suggestion of kind "pitch" holding the message for each channel they can be reached on. Nothing
is sent until the founder sends it (one by one, or "Send all reviewed")."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deal import AgentProposal, CreatorDeal, DealEvent

DM_CHANNELS = ("instagram", "twitter", "linkedin")


def auto_channel(d: CreatorDeal, lead: Optional[dict]) -> str:
    """How to reach them when the founder hasn't picked: email if we have it, else the first DM we can open."""
    if d.channel:
        return d.channel
    if d.contact_email:
        return "email"
    socials = (lead or {}).get("socials") or {}
    return next((c for c in ("instagram", "twitter", "linkedin") if socials.get(c)), "other")


def texts_from_bundle(bundle: dict) -> dict:
    """{channel: {"subject"?, "body"}} for the channels the pitch has."""
    out = {}
    email = bundle.get("email") or {}
    if email.get("body"):
        out["email"] = {"subject": email.get("subject") or "", "body": email["body"]}
    for c in DM_CHANNELS:
        if (bundle.get(c) or {}).get("body"):
            out[c] = {"body": bundle[c]["body"]}
    return out


def pick_text(texts: dict, channel: str) -> dict:
    """The message for a channel; WhatsApp and others use the shortest DM, else the email."""
    if channel in texts:
        return texts[channel]
    for c in ("instagram", "twitter", "linkedin", "email"):
        if c in texts:
            return {"body": texts[c]["body"]} if channel != "email" else texts[c]
    return {"body": ""}


async def drafts_from_job(db: AsyncSession, job, results: dict, leads_by_id: dict) -> int:
    """Adds a "pitch" draft to each creator's chat for this pitch run (skipped when you already wrote to them).
    `results`: {creator_id: {"status", "pitch_bundle"}}. The caller commits. → drafts added"""
    deals = {d.creator_id: d for d in (await db.execute(select(CreatorDeal).where(
        CreatorDeal.campaign_id == job.campaign_id, CreatorDeal.creator_id.in_(list(results))))).scalars()}
    if not deals:
        return 0
    wrote = set((await db.execute(select(DealEvent.deal_id).where(
        DealEvent.deal_id.in_([d.deal_id for d in deals.values()]), DealEvent.type == "message_sent"))).scalars())
    n = 0
    for cid, res in results.items():
        d = deals.get(cid)
        texts = texts_from_bundle((res or {}).get("pitch_bundle") or {})
        if d is None or d.deal_id in wrote or not texts:
            continue
        channel = auto_channel(d, leads_by_id.get(cid))
        first = pick_text(texts, channel)
        problems = [] if (res or {}).get("status") == "completed" else list((res or {}).get("validation_errors") or ["not checked"])
        await db.execute(pg_insert(AgentProposal).values(
            campaign_id=d.campaign_id, deal_id=d.deal_id, key=f"pitch:{job.outreach_job_id}", kind="pitch", status="pending",
            title="First message", reason=((res.get("pitch_bundle") or {}).get("pitch_angle") or None),
            payload={"message": first.get("body"), "subject": first.get("subject") or (texts.get("email") or {}).get("subject"),
                     "texts": texts, "source": "ai", "seen": False,
                     # failed the checks even after one repair: the founder must read and fix it ("Send all" skips it)
                     "needs_review": bool(problems), "problems": problems[:5]},
        ).on_conflict_do_nothing(constraint="uq_agent_proposals_deal_key"))
        n += 1
    return n

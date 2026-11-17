"""Permissions the founder gives their agent in the browser (F9.8, 8b).

    agent:   request_permission → a pending grant and a link
    founder: opens the link signed in, reads what it means in plain words, lowers the limits if they like, approves or denies
    agent:   works inside the grant until it ends or the founder removes it (the Agents page)

A grant that changes how a campaign behaves (my agent writes replies, my agent may send) writes through to that campaign's
settings, so everything built before keeps working; ending the grant switches them off again. Abilities that are checked
only when a tool runs (first emails, autopilot, deals and Track) are looked up in the table at that moment."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import constants as A
from app.auth.device import ALPHABET, clean_name, normalize_user_code
from app.models.agent_grant import AgentGrant
from app.models.campaign import Campaign

REQUEST_TTL_MINUTES = 30
MAX_PENDING_PER_USER = 20
DEFAULT_DAYS = 7
MAX_DAYS = 30

# What each ability is, in the words the founder reads. `sends`: it can send mail, so it has a daily limit and a mode.
ABILITIES: dict[str, dict] = {
    "write_replies": {"label": "Write replies and follow-ups", "sends": False,
                      "ask": "Write replies and follow-ups for this campaign with its own AI. ReachAI checks every draft; nothing is sent."},
    "send_replies": {"label": "Send replies and follow-ups", "sends": True, "per_day": (1, A.AGENT_SENDS_PER_DAY),
                     "ask": "Send replies and follow-ups it wrote from your Gmail, one at a time, only after you say yes in your chat with it.",
                     "unattended": "Send replies and follow-ups it wrote from your Gmail by itself, without asking you each time. ReachAI "
                                   "checks each one first and you get an email for every message."},
    "send_first_emails": {"label": "Send first emails", "sends": True, "per_day": (1, 20),
                          "ask": "Send first emails it wrote from your Gmail, one at a time, only after you say yes in your chat with it.",
                          "unattended": "Send first emails it wrote from your Gmail by itself, without asking you each time. ReachAI checks "
                                        "each one first and you get an email for every message."},
    "autopilot": {"label": "Control autopilot", "sends": False,
                  "ask": "Turn ReachAI's autopilot on or off for this campaign. Autopilot sends first emails and follow-ups with ReachAI's own AI."},
    "manage_campaign": {"label": "Manage the campaign", "sends": False,
                        "ask": "Add creators to your deals and set up your Track goal and signup snippet for this campaign."},
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(t: Optional[datetime]) -> Optional[datetime]:
    return t.replace(tzinfo=timezone.utc) if t is not None and t.tzinfo is None else t


def describe(g: AgentGrant) -> str:
    spec = ABILITIES[g.ability]
    text = spec["unattended"] if g.mode == "unattended" and "unattended" in spec else spec["ask"]
    return text + (f" Up to {g.per_day} a day." if spec["sends"] and g.per_day else "")


def view(g: AgentGrant, campaign_name: Optional[str] = None) -> dict:
    spec = ABILITIES.get(g.ability, {"label": g.ability, "sends": False})
    return {"id": g.grant_id, "ability": g.ability, "label": spec["label"], "what": describe(g) if g.ability in ABILITIES else "",
            "campaign_id": g.campaign_id, "campaign_name": campaign_name, "mode": g.mode, "per_day": g.per_day,
            "client_name": g.client_name, "status": g.status, "user_code": g.user_code if g.status == "pending" else None,
            "valid_until": g.valid_until.isoformat() if g.valid_until else None,
            "approved_at": g.approved_at.isoformat() if g.approved_at else None,
            "requested_days": g.requested_days, "can_unattended": "unattended" in spec}


def is_active(g: Optional[AgentGrant], now: Optional[datetime] = None) -> bool:
    return bool(g and g.status == "approved" and _aware(g.valid_until) and _aware(g.valid_until) > (now or _now()))


async def request(db: AsyncSession, user_id: str, *, ability: str, campaign_id: Optional[str], days: int, mode: str,
                  per_day: Optional[int], client_name: Optional[str]) -> AgentGrant:
    """A pending request. Raises HTTPException with a message that tells the agent what to fix."""
    import secrets

    spec = ABILITIES.get(ability)
    if spec is None:
        raise HTTPException(422, f"Unknown ability. Choose one of: {', '.join(ABILITIES)}.")
    if not campaign_id:
        raise HTTPException(422, "A permission is for one campaign: give its campaign_id.")
    camp = await db.scalar(select(Campaign.campaign_id).where(Campaign.campaign_id == campaign_id, Campaign.user_id == user_id))
    if camp is None:
        raise HTTPException(404, "Campaign not found.")
    if mode not in ("ask", "unattended") or (mode == "unattended" and "unattended" not in spec):
        raise HTTPException(422, "mode is 'ask' (the founder says yes in chat each time) or, for sending, 'unattended'.")
    lo, hi = spec.get("per_day", (None, None))
    if spec["sends"]:
        per_day = max(lo, min(hi, per_day or hi))
    else:
        per_day = None
    now = _now()
    pending = len((await db.execute(select(AgentGrant.grant_id).where(AgentGrant.user_id == user_id, AgentGrant.status == "pending",
                                                                       AgentGrant.request_expires_at > now))).all())
    if pending >= MAX_PENDING_PER_USER:
        raise HTTPException(429, "There are already many requests waiting for the founder. Ask them to look at the Agents page.")
    for _ in range(5):
        letters = "".join(secrets.choice(ALPHABET) for _ in range(8))
        code = f"{letters[:4]}-{letters[4:]}"
        if not await db.scalar(select(AgentGrant.grant_id).where(AgentGrant.user_code == code)):
            break
    g = AgentGrant(user_id=user_id, campaign_id=campaign_id, ability=ability, mode=mode, per_day=per_day,
                   client_name=clean_name(client_name), user_code=code, requested_days=max(1, min(MAX_DAYS, days or DEFAULT_DAYS)),
                   request_expires_at=now + timedelta(minutes=REQUEST_TTL_MINUTES))
    db.add(g)
    await db.commit()
    return g


async def lookup(db: AsyncSession, user_id: str, raw_code: str) -> dict:
    code = normalize_user_code(raw_code)
    g = (await db.execute(select(AgentGrant).where(AgentGrant.user_code == code, AgentGrant.user_id == user_id))).scalar_one_or_none() if code else None
    if g is None or g.status != "pending" or _aware(g.request_expires_at) <= _now():
        raise HTTPException(404, "That request isn't valid any more. Ask your agent to ask again.")
    name = await db.scalar(select(Campaign.name).where(Campaign.campaign_id == g.campaign_id))
    return {**view(g, name), "max_days": MAX_DAYS, "per_day_range": ABILITIES[g.ability].get("per_day")}


async def decide(db: AsyncSession, user_id: str, raw_code: str, approve: bool, *, days: Optional[int] = None,
                 per_day: Optional[int] = None, mode: Optional[str] = None) -> dict:
    """Approve (with limits no looser than what was asked) or deny, once. Applies what the grant switches on."""
    code = normalize_user_code(raw_code)
    now = _now()
    g = (await db.execute(select(AgentGrant).where(AgentGrant.user_code == code, AgentGrant.user_id == user_id,
                                                   AgentGrant.status == "pending", AgentGrant.request_expires_at > now))).scalar_one_or_none() if code else None
    if g is None:
        raise HTTPException(404, "That request isn't valid any more. Ask your agent to ask again.")
    spec = ABILITIES[g.ability]
    if approve:
        g.requested_days = max(1, min(g.requested_days, days or g.requested_days, MAX_DAYS))  # only shorter than asked, never longer
        if spec["sends"] and per_day:
            g.per_day = max(1, min(g.per_day or per_day, per_day))
        if mode == "ask":
            g.mode = "ask"  # the founder can make it stricter, never looser
        g.status, g.approved_at, g.valid_until = "approved", now, now + timedelta(days=g.requested_days)
        await _apply(db, g)
    else:
        g.status = "denied"
    await db.commit()
    return {"approved": approve, "valid_until": g.valid_until.isoformat() if g.valid_until else None}


async def _settings(db: AsyncSession, campaign_id: str) -> tuple[Optional[Campaign], dict]:
    camp = await db.get(Campaign, campaign_id)
    return camp, dict(camp.outreach_settings or {}) if camp else {}


SEND_KEYS = ("agent_send", "agent_send_mode", "agent_send_per_day", "agent_send_grant")


async def _apply(db: AsyncSession, g: AgentGrant) -> None:
    """Switches on what this grant gives, in the campaign's settings. A grant only "owns" the writer switch when it was the
    one that turned it on, so ending it never undoes something the founder set themselves."""
    if g.ability not in ("write_replies", "send_replies"):
        return
    camp, s = await _settings(db, g.campaign_id)
    if camp is None:
        return
    owners = dict(s.get("grants") or {})
    if s.get("writer") != "agent":
        s["writer"] = "agent"
        owners["writer"] = g.grant_id
    if g.ability == "send_replies":
        s.update(agent_send=True, agent_send_mode=g.mode, agent_send_per_day=g.per_day, agent_send_grant=g.grant_id)
    s["grants"] = owners
    camp.outreach_settings = s


async def _unapply(db: AsyncSession, g: AgentGrant) -> None:
    camp, s = await _settings(db, g.campaign_id) if g.campaign_id else (None, {})
    if camp is None:
        return
    owners = dict(s.get("grants") or {})
    changed = False
    if g.ability == "send_replies" and s.get("agent_send_grant") == g.grant_id:
        for k in SEND_KEYS:
            s.pop(k, None)
        changed = True
    if owners.get("writer") == g.grant_id:  # this grant turned "my agent writes" on: turn it off, and sending with it
        s["writer"] = "reachai"
        for k in SEND_KEYS:
            s.pop(k, None)
        owners.pop("writer", None)
        s["grants"] = owners
        changed = True
    if changed:
        camp.outreach_settings = s


async def revoke(db: AsyncSession, user_id: str, grant_id: str) -> dict:
    g = (await db.execute(select(AgentGrant).where(AgentGrant.grant_id == grant_id, AgentGrant.user_id == user_id))).scalar_one_or_none()
    if g is None:
        raise HTTPException(404, "Permission not found.")
    if g.status in ("approved", "pending"):
        was_approved = g.status == "approved"
        g.status, g.revoked_at = "revoked", _now()
        if was_approved:
            await _unapply(db, g)
        await db.commit()
    return {"revoked": True}


async def expire_due(db: AsyncSession, now: Optional[datetime] = None) -> int:
    """Ends grants whose time is up and switches off what they switched on. Run hourly; tools also check the end date."""
    now = now or _now()
    rows = (await db.execute(select(AgentGrant).where(AgentGrant.status == "approved", AgentGrant.valid_until <= now))).scalars().all()
    for g in rows:
        g.status = "revoked"
        g.revoked_at = now
        await _unapply(db, g)
    await db.commit()
    return len(rows)


async def active(db: AsyncSession, user_id: str, ability: str, campaign_id: str) -> Optional[AgentGrant]:
    now = _now()
    rows = (await db.execute(select(AgentGrant).where(AgentGrant.user_id == user_id, AgentGrant.ability == ability,
                                                      AgentGrant.campaign_id == campaign_id, AgentGrant.status == "approved")
                             .order_by(AgentGrant.valid_until.desc()))).scalars().all()
    return next((g for g in rows if is_active(g, now)), None)


async def listing(db: AsyncSession, user_id: str) -> list[dict]:
    rows = (await db.execute(select(AgentGrant, Campaign.name).join(Campaign, Campaign.campaign_id == AgentGrant.campaign_id, isouter=True)
                             .where(AgentGrant.user_id == user_id, AgentGrant.status.in_(("pending", "approved")))
                             .order_by(AgentGrant.created_at.desc()))).all()
    now = _now()
    return [view(g, name) for g, name in rows
            if (g.status == "approved" and is_active(g, now)) or (g.status == "pending" and _aware(g.request_expires_at) > now)]

"""Device login (F9.8, 8a): connect an agent or CLI to a ReachAI account without copying a key.

    agent:   start  → gets a secret `device_code` (kept) and a short `user_code` + link (shown to the founder)
    founder: opens the link signed in, sees who is asking, approves or denies (once, in the browser)
    agent:   polls  → once approved, receives its own personal API key (shown once, revocable on the Agents page)

The founder's approval is the consent: an agent cannot approve its own request, because approving needs the website's
sign-in and no personal key is accepted on those endpoints (app/auth/api_key_access.py)."""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.auth import generate_api_key
from app.models.api_key import ApiKey
from app.models.device_code import DeviceCode

CODE_TTL_MINUTES = 10
POLL_INTERVAL_S = 5
STARTS_PER_IP_PER_HOUR = 10
MAX_PENDING = 2000
MAX_ACTIVE_KEYS = 10  # same limit as keys made in the app
ALPHABET = "BCDFGHJKLMNPQRSTVWXZ"  # no vowels: a code can't spell a word; no look-alikes
CLIENT_NAME_MAX = 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(t: Optional[datetime]) -> Optional[datetime]:
    return t.replace(tzinfo=timezone.utc) if t is not None and t.tzinfo is None else t


def hash_secret(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def clean_name(raw: Optional[str]) -> str:
    """What the agent calls itself, as plain text (it is shown to the founder, so it can't carry markup or tricks)."""
    name = re.sub(r"[^\w .,'()+/-]", "", (raw or ""), flags=re.UNICODE)
    name = " ".join(name.split())[:CLIENT_NAME_MAX]
    return name or "An agent"


def normalize_user_code(raw: Optional[str]) -> str:
    letters = re.sub(r"[^A-Za-z]", "", raw or "").upper()
    return f"{letters[:4]}-{letters[4:8]}" if len(letters) == 8 else ""


def _new_user_code() -> str:
    letters = "".join(secrets.choice(ALPHABET) for _ in range(8))
    return f"{letters[:4]}-{letters[4:]}"


async def start(db: AsyncSession, client_name: Optional[str], ip: Optional[str]) -> dict:
    now = _now()
    ip_hash = hash_secret("ip:" + ip) if ip else None
    await db.execute(delete(DeviceCode).where(DeviceCode.expires_at < now - timedelta(days=1)))  # tidy up old rows
    if ip_hash:
        recent = await db.scalar(select(func.count()).select_from(DeviceCode).where(
            DeviceCode.ip_hash == ip_hash, DeviceCode.created_at >= now - timedelta(hours=1)))
        if (recent or 0) >= STARTS_PER_IP_PER_HOUR:
            raise HTTPException(429, "Too many sign-in requests from this address. Try again in an hour.")
    pending = await db.scalar(select(func.count()).select_from(DeviceCode).where(DeviceCode.status == "pending", DeviceCode.expires_at > now))
    if (pending or 0) >= MAX_PENDING:
        raise HTTPException(503, "Too many sign-ins are waiting right now. Try again in a few minutes.")
    secret = secrets.token_urlsafe(32)
    for _ in range(5):
        code = _new_user_code()
        if not await db.scalar(select(DeviceCode.code_id).where(DeviceCode.user_code == code)):
            break
    row = DeviceCode(device_hash=hash_secret(secret), user_code=code, client_name=clean_name(client_name), ip_hash=ip_hash,
                     expires_at=now + timedelta(minutes=CODE_TTL_MINUTES))
    db.add(row)
    await db.commit()
    return {"device_code": secret, "user_code": code, "expires_in": CODE_TTL_MINUTES * 60, "interval": POLL_INTERVAL_S}


async def poll(db: AsyncSession, device_code: str) -> dict:
    """pending | slow_down | denied | expired | used | approved (with the key, once)."""
    now = _now()
    row = (await db.execute(select(DeviceCode).where(DeviceCode.device_hash == hash_secret(device_code or "")))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Unknown code. Start again.")
    if _aware(row.expires_at) <= now and row.key_id is None:
        return {"status": "expired"}
    last = _aware(row.last_polled_at)
    too_fast = last is not None and (now - last).total_seconds() < POLL_INTERVAL_S - 1
    row.last_polled_at = now
    if row.status == "denied":
        await db.commit()
        return {"status": "denied"}
    if row.status != "approved":
        await db.commit()
        return {"status": "slow_down" if too_fast else "pending", "interval": POLL_INTERVAL_S}
    key_id = secrets.token_hex(16)
    taken = await db.execute(update(DeviceCode).where(DeviceCode.code_id == row.code_id, DeviceCode.key_id.is_(None),
                                                      DeviceCode.status == "approved").values(key_id=key_id))
    if taken.rowcount != 1:  # another poll already took it: a key is shown only once
        await db.commit()
        return {"status": "used"}
    active = await db.scalar(select(func.count()).select_from(ApiKey).where(ApiKey.user_id == row.user_id, ApiKey.revoked_at.is_(None)))
    if (active or 0) >= MAX_ACTIVE_KEYS:
        await db.execute(update(DeviceCode).where(DeviceCode.code_id == row.code_id).values(key_id=None))
        await db.commit()
        raise HTTPException(409, f"This account already has {MAX_ACTIVE_KEYS} active keys. Revoke one on the Agents page, then try again.")
    token, prefix, digest = generate_api_key()
    db.add(ApiKey(key_id=key_id, user_id=row.user_id, name=f"{row.client_name} (device login)"[:60], prefix=prefix, key_hash=digest))
    await db.commit()
    return {"status": "approved", "api_key": token}


async def lookup(db: AsyncSession, raw_code: str) -> dict:
    code = normalize_user_code(raw_code)
    row = (await db.execute(select(DeviceCode).where(DeviceCode.user_code == code))).scalar_one_or_none() if code else None
    if row is None or _aware(row.expires_at) <= _now() or row.status != "pending":
        raise HTTPException(404, "That code isn't valid any more. Ask your agent for a new one.")
    return {"user_code": row.user_code, "client_name": row.client_name,
            "asked_at": row.created_at.isoformat() if row.created_at else None}


async def decide(db: AsyncSession, user_id: str, raw_code: str, approve: bool) -> dict:
    """Approve or deny, once. Only a pending, unexpired code can be decided."""
    code = normalize_user_code(raw_code)
    now = _now()
    done = await db.execute(update(DeviceCode).where(DeviceCode.user_code == code, DeviceCode.status == "pending",
                                                     DeviceCode.expires_at > now)
                            .values(status="approved" if approve else "denied", user_id=user_id, approved_at=now))
    await db.commit()
    if done.rowcount != 1:
        raise HTTPException(404, "That code isn't valid any more. Ask your agent for a new one.")
    return {"approved": approve}

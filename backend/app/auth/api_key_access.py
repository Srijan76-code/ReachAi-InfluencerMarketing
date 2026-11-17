"""Personal API keys on the REST API (F9.8, 8a).

A key (`rai_...`, made on the Agents page or by a device login) works on the MCP server, and now on a short allowlist of
REST routes. Everything else is refused, whatever the key: default deny. In particular a key can never reach the routes
that make or approve keys, that move money or change a plan, that agree, close or pay a deal, or that send a message
(those need the founder in the website, or a grant they approve there: F9.8 8b)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select

from app.mcp.auth import API_KEY_PREFIX, hash_key
from app.models.api_key import ApiKey
from app.models.user import User

_ID = r"[^/]+"
ALLOWED: list[tuple[str, re.Pattern]] = [(m, re.compile(p)) for m, p in [
    ("GET", r"^/api/campaigns/?$"),
    ("GET", rf"^/api/campaigns/{_ID}/(details|status|leads|skipped|deals|track|autopilot)$"),
    ("GET", r"^/api/inbox$"),
    ("GET", r"^/api/billing/(balance|history)$"),
    ("GET", rf"^/api/billing/quote/{_ID}$"),
    ("GET", r"^/api/gmail$"),
    ("POST", r"^/api/campaigns/create$"),  # an empty draft
    ("POST", r"^/api/campaigns/brief-from-url$"),  # reads a website into brief fields (20 a day)
]]


def is_allowed(method: str, path: str) -> bool:
    return any(method == m and p.match(path) for m, p in ALLOWED)


async def user_for_key(session_factory, token: str, method: str, path: str) -> dict:
    """The sign-in claims (`sub` = the Clerk id, as for a website session) for a valid key on an allowed route.
    401 for a key that isn't valid, 403 for a route a key may not use."""
    async with session_factory() as db:
        row = (await db.execute(select(ApiKey, User.clerk_id).join(User, User.user_id == ApiKey.user_id)
                                .where(ApiKey.key_hash == hash_key(token), ApiKey.revoked_at.is_(None)))).first()
        if row is None:
            raise HTTPException(401, "That API key isn't valid or was revoked.")
        if not is_allowed(method, path):
            raise HTTPException(403, "An API key can't use this endpoint. Use the MCP connection, or the ReachAI website.")
        key, clerk_id = row
        key.last_used_at = datetime.now(timezone.utc)
        await db.commit()
        return {"sub": clerk_id, "via": "api_key", "key_id": key.key_id}


def bearer_key(auth_header: Optional[str]) -> Optional[str]:
    """The key from an `Authorization: Bearer rai_...` header. A key is never accepted in a URL (URLs get logged)."""
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        return token if token.startswith(API_KEY_PREFIX) else None
    return None

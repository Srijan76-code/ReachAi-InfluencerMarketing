"""Who is calling the MCP server?

Three kinds of bearer token reach `/api/mcp`:
- A Clerk OAuth access token from the sign-in flow (claude.ai, ChatGPT, Cursor, Claude Code). Clerk
  issues it as a signed JWT (`eyJ...`) when the instance has JWT access tokens on, which ours does,
  or as an opaque `oat_...` token otherwise. Both are accepted.
- `rai_...`: a personal API key made in the app, for agents that cannot do OAuth.
Anything else is refused. Both resolve to one ReachAI user, and every tool runs as that user.
"""

import asyncio
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Awaitable, Callable

import jwt
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy import select

from app.mcp import config
from app.mcp.db import session_scope
from app.models.api_key import ApiKey

logger = logging.getLogger(__name__)

API_KEY_PREFIX = "rai_"
CLERK_OAUTH_PREFIX = "oat_"
KEY_DISPLAY_CHARS = 12  # "rai_" + 8 characters, shown in the key list

# Signing algorithms Clerk uses for access tokens. Never accept "none" or HMAC.
JWT_ALGORITHMS = ["RS256"]
JWT_LEEWAY_SECONDS = 30

ClerkVerify = Callable[[str], Awaitable[dict[str, Any] | None]]
UserResolver = Callable[[str], Awaitable[str | None]]


def hash_key(token: str) -> str:
    # Keys are 256-bit random values, so an unsalted SHA-256 is enough (nothing to brute force).
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Returns (plaintext, display prefix, hash). The plaintext is shown to the user once."""
    token = API_KEY_PREFIX + secrets.token_urlsafe(32)
    return token, token[:KEY_DISPLAY_CHARS], hash_key(token)


async def verify_with_clerk(token: str) -> dict[str, Any] | None:
    """Ask Clerk whether this OAuth access token is valid. Returns its payload, or None."""
    secret = config.clerk_secret_key()
    if not secret:
        logger.warning("CLERK_SECRET_KEY is not set; Clerk OAuth tokens cannot be verified")
        return None
    from clerk_backend_api.security import TokenVerificationError, VerifyTokenOptions, verify_token_async

    try:
        return await verify_token_async(token, VerifyTokenOptions(secret_key=secret))
    except TokenVerificationError as exc:
        logger.info("Clerk OAuth token rejected: %s", getattr(exc, "reason", "invalid"))
        return None


@lru_cache(maxsize=1)
def _jwks_client() -> jwt.PyJWKClient:
    # Keys are cached in memory, so a warm instance verifies tokens without calling Clerk.
    return jwt.PyJWKClient(f"{config.clerk_issuer_url()}/.well-known/jwks.json", cache_keys=True)


def _signing_key(token: str) -> Any:
    return _jwks_client().get_signing_key_from_jwt(token).key


def looks_like_jwt(token: str) -> bool:
    return token.startswith("eyJ") and token.count(".") == 2


async def verify_clerk_jwt(token: str, key_for: Callable[[str], Any] = _signing_key) -> dict[str, Any] | None:
    """Check a Clerk JWT access token: signature, expiry, issuer, and that it was issued for this server.

    The audience must be exactly this server's MCP URL. That also refuses the web app's own session
    tokens, which carry no such audience.
    """
    try:
        key = await asyncio.to_thread(key_for, token)
        return jwt.decode(
            token,
            key,
            algorithms=JWT_ALGORITHMS,
            audience=config.public_url(),
            issuer=config.clerk_issuer_url(),
            leeway=JWT_LEEWAY_SECONDS,
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
    except (jwt.PyJWTError, ValueError) as exc:
        logger.info("Clerk JWT access token rejected: %s", type(exc).__name__)
        return None


async def clerk_user_to_user_id(clerk_id: str) -> str | None:
    """Map a Clerk user id to our users row (created on first use, like the web app does)."""
    from app.auth.user import get_db_user

    user = await get_db_user({"sub": clerk_id})
    return user.user_id if user else None


def _audience_ok(payload: dict[str, Any]) -> bool:
    """If Clerk reports who the token was issued for, it must be this server."""
    audience = payload.get("aud") or payload.get("audience")
    if not audience:
        return True
    values = [audience] if isinstance(audience, str) else list(audience)
    return config.public_url() in [str(v).rstrip("/") for v in values]


class ReachAITokenVerifier:
    """Implements the MCP SDK's `TokenVerifier` protocol."""

    def __init__(
        self,
        clerk_verify: ClerkVerify = verify_with_clerk,
        resolve_user: UserResolver = clerk_user_to_user_id,
        clerk_jwt_verify: ClerkVerify = verify_clerk_jwt,
    ):
        self._clerk_verify = clerk_verify
        self._resolve_user = resolve_user
        self._clerk_jwt_verify = clerk_jwt_verify

    async def verify_token(self, token: str) -> AccessToken | None:
        if token.startswith(API_KEY_PREFIX):
            return await self._verify_api_key(token)
        if token.startswith(CLERK_OAUTH_PREFIX):
            return await self._verify_clerk(await self._clerk_verify(token), token)
        if looks_like_jwt(token):
            return await self._verify_clerk(await self._clerk_jwt_verify(token), token)
        return None

    async def _verify_api_key(self, token: str) -> AccessToken | None:
        async with session_scope() as db:
            result = await db.execute(
                select(ApiKey).where(ApiKey.key_hash == hash_key(token), ApiKey.revoked_at.is_(None))
            )
            key = result.scalar_one_or_none()
            if key is None:
                return None
            now = datetime.now(timezone.utc)
            last = key.last_used_at
            if last is not None and last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if last is None or now - last > timedelta(seconds=config.API_KEY_TOUCH_SECONDS):
                key.last_used_at = now
                await db.commit()
            user_id = key.user_id
        return AccessToken(
            token=token,
            client_id="api-key",
            scopes=[],
            subject=user_id,
            claims={"user_id": user_id, "auth": "api_key"},
        )

    async def _verify_clerk(self, payload: dict[str, Any] | None, token: str) -> AccessToken | None:
        if not payload or payload.get("revoked") or payload.get("expired") or not _audience_ok(payload):
            return None
        clerk_id = payload.get("subject") or payload.get("sub")
        if not clerk_id:
            return None
        user_id = await self._resolve_user(str(clerk_id))
        if not user_id:
            return None
        return AccessToken(
            token=token,
            client_id=str(payload.get("client_id") or "clerk-oauth"),
            scopes=_scopes(payload),
            subject=user_id,
            claims={"user_id": user_id, "auth": "oauth"},
        )


def _scopes(payload: dict[str, Any]) -> list[str]:
    # Opaque tokens list "scopes"; JWT access tokens carry a space-separated "scope" (RFC 9068).
    if payload.get("scopes"):
        return [str(x) for x in payload["scopes"]]
    return str(payload.get("scope") or "").split()


def current_user_id() -> str:
    """The ReachAI user making this tool call. Raises if the request was not authenticated."""
    access = get_access_token()
    user_id = (access.claims or {}).get("user_id") if access else None
    if not user_id:
        raise ToolError("Not signed in to ReachAI")
    return str(user_id)

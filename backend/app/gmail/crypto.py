"""Encrypting stored Gmail tokens and signing the sign-in state. The key is TOKEN_ENCRYPTION_KEY (a Fernet
key) when set, else derived from GOOGLE_OAUTH_CLIENT_SECRET, so connecting Gmail needs no extra setup; rotating
that secret means everyone reconnects. Keys are never logged (rule 8)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.gmail import constants as G


class NotConfigured(RuntimeError):
    pass


def _secret() -> bytes:
    explicit = os.getenv("TOKEN_ENCRYPTION_KEY")
    if explicit:
        return explicit.encode()
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
    if not client_secret:
        raise NotConfigured("Gmail isn't set up on this server.")
    digest = hashlib.sha256(b"reachai-gmail-token-key:" + client_secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def _fernet() -> Fernet:
    return Fernet(_secret())


def encrypt(text: str) -> str:
    return _fernet().encrypt(text.encode()).decode()


def decrypt(token: str) -> Optional[str]:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None


def _mac(body: bytes) -> str:
    return base64.urlsafe_b64encode(hmac.new(_secret(), body, hashlib.sha256).digest()).decode().rstrip("=")


def sign_state(user_id: str, return_to: str, now: Optional[float] = None) -> str:
    body = base64.urlsafe_b64encode(json.dumps(
        {"u": user_id, "r": return_to, "t": int(now or time.time()), "n": os.urandom(8).hex()}
    ).encode()).decode().rstrip("=")
    return f"{body}.{_mac(body.encode())}"


def verify_state(state: str, now: Optional[float] = None) -> Optional[dict]:
    """{"u": user_id, "r": return_to} if the state is ours, untampered and recent; else None."""
    try:
        body, mac = state.split(".", 1)
        if not hmac.compare_digest(mac, _mac(body.encode())):
            return None
        data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except Exception:
        return None
    if (now or time.time()) - data.get("t", 0) > G.STATE_MAX_AGE_SECONDS:
        return None
    return data

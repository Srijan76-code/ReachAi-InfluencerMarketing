"""Clerk tokens live about a minute: one that expired a few seconds ago (slow start, clock drift) still works;
a really old one doesn't."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from starlette.requests import Request


def _request(token):
    return Request({"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())], "query_string": b""})


@pytest.mark.asyncio
async def test_expiry_leeway(monkeypatch):
    from app.auth import user as U

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    class Jwks:
        def get_signing_key_from_jwt(self, token):
            return type("K", (), {"key": key.public_key()})()

    monkeypatch.setattr(U, "jwks_client", Jwks())
    now = int(time.time())
    fresh_enough = jwt.encode({"sub": "u1", "exp": now - 20}, key, algorithm="RS256")
    assert (await U.get_current_user(_request(fresh_enough)))["sub"] == "u1"
    old = jwt.encode({"sub": "u1", "exp": now - U.JWT_LEEWAY_SECONDS - 30}, key, algorithm="RS256")
    with pytest.raises(HTTPException) as e:
        await U.get_current_user(_request(old))
    assert e.value.detail == "Token has expired"

"""Clerk JWT access tokens (what claude.ai and ChatGPT get from the sign-in flow)."""

import time

import httpx
import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.applications import Starlette

from app.mcp import auth as mcp_auth
from app.mcp.server import create_server, mcp_routes
from tests.mcp.conftest import rpc

pytestmark = pytest.mark.asyncio

AUD = "https://reachai.test/api/mcp"
ISS = "https://clerk.reachai.test"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def token(key=KEY, alg="RS256", **overrides):
    now = int(time.time())
    claims = {"iss": ISS, "sub": "clerk_1", "aud": AUD, "iat": now, "exp": now + 600,
              "client_id": "claude", "scope": "profile email"}
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm=alg)


def public_key(_token):
    return KEY.public_key()


async def verify(t):
    return await mcp_auth.verify_clerk_jwt(t, key_for=public_key)


async def test_valid_token_is_accepted():
    payload = await verify(token())
    assert payload["sub"] == "clerk_1"


@pytest.mark.parametrize("bad", [
    {"aud": "https://elsewhere.test/mcp"},  # issued for another server
    {"aud": None},  # the web app's own session token has no such audience
    {"iss": "https://evil.test"},
    {"exp": int(time.time()) - 120},
    {"sub": None},
])
async def test_wrong_claims_are_refused(bad):
    assert await verify(token(**bad)) is None


async def test_wrong_signature_or_algorithm_is_refused():
    assert await verify(token(key=OTHER_KEY)) is None
    assert await verify(token(key="a-shared-secret-that-is-long-enough-for-hs256", alg="HS256")) is None
    assert await verify("eyJhbGciOi.fake.jwt") is None


@pytest_asyncio.fixture
async def jwt_client(db, clerk):
    verifier = mcp_auth.ReachAITokenVerifier(clerk_verify=clerk.verify, resolve_user=clerk.resolve, clerk_jwt_verify=verify)
    app = Starlette(routes=mcp_routes(create_server(verifier)))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://reachai.test") as c:
        yield c


async def test_jwt_token_works_over_mcp(jwt_client):
    assert (await rpc(jwt_client, token(), "tools/list")).status_code == 200
    assert (await rpc(jwt_client, token(aud="https://elsewhere.test/mcp"), "tools/list")).status_code == 401
    assert (await rpc(jwt_client, token(sub="clerk_999"), "tools/list")).status_code == 401

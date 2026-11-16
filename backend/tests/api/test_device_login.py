"""Device login and keys on the REST API (F9.8, 8a): an agent asks, the founder approves once in the browser, the agent
gets its own key; a key works only on an allowlist of routes and can never approve itself."""

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from app.auth import device
from app.mcp.auth import generate_api_key
from app.models.api_key import ApiKey
from app.models.device_code import DeviceCode
from app.models.user import User
from tests.discovery.conftest import create_tables, make_engine

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def env(tmp_path, monkeypatch):
    from app.auth import user as auth
    from app.db import database
    from app.main import app

    engine, is_pg = make_engine(tmp_path)
    await create_tables(engine, is_pg, ["users", "api_keys", "device_codes", "connected_accounts"])
    sf = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as s:
        s.add(User(user_id="u1", clerk_id="clerk-1"))
        await s.commit()

    async def get_db():
        async with sf() as session:
            yield session

    state = {"clerk": None}

    async def me():
        return {"sub": state["clerk"]}

    auth._USER_CACHE.clear()
    monkeypatch.setattr(auth, "AsyncSessionLocal", sf)
    app.dependency_overrides[database.get_db] = get_db

    class Env:
        pass

    e = Env()
    e.sf = sf

    def as_founder(on=True):
        """Sign the website session in as the founder (Clerk), or out."""
        state["clerk"] = "clerk-1" if on else None
        if on:
            app.dependency_overrides[auth.get_current_user] = me
        else:
            app.dependency_overrides.pop(auth.get_current_user, None)

    e.as_founder = as_founder
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        e.c = c
        yield e
    app.dependency_overrides.clear()
    auth._USER_CACHE.clear()
    await engine.dispose()


async def start(e, name="Claude Code", ip="1.2.3.4"):
    return (await e.c.post("/api/device/start", json={"client_name": name}, headers={"x-forwarded-for": ip})).json()


async def approved_key(e):
    s = await start(e)
    e.as_founder(True)
    assert (await e.c.post("/api/device/decision", json={"code": s["user_code"], "approve": True})).status_code == 200
    e.as_founder(False)
    done = (await e.c.post("/api/device/poll", json={"device_code": s["device_code"]})).json()
    return s, done["api_key"]


# --- starting and polling -----------------------------------------------------------------------------------

async def test_start_gives_the_agent_a_secret_and_the_founder_a_short_code(env):
    s = await start(env)
    assert len(s["device_code"]) >= 32 and s["expires_in"] == 600 and s["interval"] == 5
    a, b = s["user_code"].split("-")
    assert len(a) == 4 and len(b) == 4 and not set((a + b)) & set("AEIOU")  # no vowels: a code can't spell a word
    assert s["verification_url"].endswith(f"/device?code={s['user_code']}")
    async with env.sf() as db:
        row = (await db.execute(select(DeviceCode))).scalar_one()
    assert row.device_hash != s["device_code"] and s["device_code"] not in str(row.__dict__)  # only the hash is stored


async def test_polling_before_approval_is_pending_and_too_fast_polling_is_told_to_slow_down(env):
    s = await start(env)
    first = (await env.c.post("/api/device/poll", json={"device_code": s["device_code"]})).json()
    second = (await env.c.post("/api/device/poll", json={"device_code": s["device_code"]})).json()
    assert first["status"] == "pending" and second["status"] == "slow_down"
    assert (await env.c.post("/api/device/poll", json={"device_code": "x" * 40})).status_code == 404


# --- the whole flow -----------------------------------------------------------------------------------------

async def test_approving_hands_the_agent_its_own_key_once_and_the_key_works(env):
    s = await start(env, name="<script>Claude</script> Code")
    env.as_founder(True)
    shown = (await env.c.get("/api/device/lookup", params={"code": s["user_code"].lower().replace("-", " ")})).json()
    assert shown["client_name"] == "scriptClaude/script Code" and not set("<>&\"") & set(shown["client_name"])  # shown as plain text
    assert (await env.c.post("/api/device/decision", json={"code": s["user_code"], "approve": True})).json() == {"approved": True}
    env.as_founder(False)
    done = (await env.c.post("/api/device/poll", json={"device_code": s["device_code"]})).json()
    key = done["api_key"]
    assert done["status"] == "approved" and key.startswith("rai_")
    assert (await env.c.post("/api/device/poll", json={"device_code": s["device_code"]})).json()["status"] == "used"  # shown once
    async with env.sf() as db:
        row = (await db.execute(select(ApiKey))).scalar_one()
    assert row.user_id == "u1" and row.name.endswith("(device login)") and row.key_hash != key
    ok = await env.c.get("/api/gmail", headers={"Authorization": f"Bearer {key}"})
    assert ok.status_code == 200 and ok.json()["connected"] is False
    async with env.sf() as db:
        assert (await db.execute(select(ApiKey.last_used_at))).scalar_one() is not None
        await db.execute(update(ApiKey).values(revoked_at=datetime.now(timezone.utc)))
        await db.commit()
    assert (await env.c.get("/api/gmail", headers={"Authorization": f"Bearer {key}"})).status_code == 401  # revoked


async def test_denied_expired_and_already_decided_codes_stop_there(env):
    s = await start(env)
    env.as_founder(True)
    assert (await env.c.post("/api/device/decision", json={"code": s["user_code"], "approve": False})).json() == {"approved": False}
    assert (await env.c.post("/api/device/decision", json={"code": s["user_code"], "approve": True})).status_code == 404  # decided once
    assert (await env.c.get("/api/device/lookup", params={"code": s["user_code"]})).status_code == 404
    env.as_founder(False)
    assert (await env.c.post("/api/device/poll", json={"device_code": s["device_code"]})).json()["status"] == "denied"

    old = await start(env, ip="5.5.5.5")
    async with env.sf() as db:
        await db.execute(update(DeviceCode).where(DeviceCode.user_code == old["user_code"]).values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
        await db.commit()
    assert (await env.c.post("/api/device/poll", json={"device_code": old["device_code"]})).json()["status"] == "expired"
    env.as_founder(True)
    assert (await env.c.post("/api/device/decision", json={"code": old["user_code"], "approve": True})).status_code == 404


async def test_two_polls_at_once_still_hand_over_exactly_one_key(env):
    s = await start(env)
    env.as_founder(True)
    await env.c.post("/api/device/decision", json={"code": s["user_code"], "approve": True})
    env.as_founder(False)
    results = await asyncio.gather(*[env.c.post("/api/device/poll", json={"device_code": s["device_code"]}) for _ in range(4)])
    statuses = sorted(r.json()["status"] for r in results)
    assert statuses.count("approved") == 1
    async with env.sf() as db:
        assert len((await db.execute(select(ApiKey))).scalars().all()) == 1


async def test_a_full_set_of_keys_keeps_the_approval_so_it_can_be_retried(env):
    async with env.sf() as db:
        for i in range(device.MAX_ACTIVE_KEYS):
            _, prefix, digest = generate_api_key()
            db.add(ApiKey(user_id="u1", name=f"k{i}", prefix=prefix, key_hash=digest))
        await db.commit()
    s = await start(env)
    env.as_founder(True)
    await env.c.post("/api/device/decision", json={"code": s["user_code"], "approve": True})
    env.as_founder(False)
    full = await env.c.post("/api/device/poll", json={"device_code": s["device_code"]})
    assert full.status_code == 409 and "Revoke one" in full.json()["detail"]
    async with env.sf() as db:
        await db.execute(update(ApiKey).where(ApiKey.name == "k0").values(revoked_at=datetime.now(timezone.utc)))
        await db.execute(update(DeviceCode).values(last_polled_at=None))
        await db.commit()
    assert (await env.c.post("/api/device/poll", json={"device_code": s["device_code"]})).json()["status"] == "approved"


async def test_one_address_can_only_start_so_many_codes_an_hour(env):
    for _ in range(device.STARTS_PER_IP_PER_HOUR):
        assert (await env.c.post("/api/device/start", json={}, headers={"x-forwarded-for": "9.9.9.9"})).status_code == 200
    assert (await env.c.post("/api/device/start", json={}, headers={"x-forwarded-for": "9.9.9.9"})).status_code == 429
    assert (await env.c.post("/api/device/start", json={}, headers={"x-forwarded-for": "8.8.8.8"})).status_code == 200


# --- a key can't approve itself, and works only on the allowlist -----------------------------------------------

async def test_an_agent_cannot_approve_its_own_request(env):
    _, key = await approved_key(env)
    s2 = await start(env, ip="7.7.7.7")
    h = {"Authorization": f"Bearer {key}"}
    assert (await env.c.post("/api/device/decision", json={"code": s2["user_code"], "approve": True}, headers=h)).status_code == 403
    assert (await env.c.get("/api/device/lookup", params={"code": s2["user_code"]}, headers=h)).status_code == 403
    assert (await env.c.post("/api/device/decision", json={"code": s2["user_code"], "approve": True})).status_code == 401  # nobody signed in


@pytest.mark.parametrize("method,path", [
    ("POST", "/api/keys"), ("DELETE", "/api/gmail"), ("POST", "/api/billing/checkout"), ("POST", "/api/billing/portal"),
    ("POST", "/api/deals/d1/agree"), ("POST", "/api/deals/d1/paid"), ("POST", "/api/proposals/p1/approve"),
    ("POST", "/api/campaigns/c1/generate"), ("PUT", "/api/campaigns/c1/autopilot"), ("DELETE", "/api/campaigns/c1"),
    ("POST", "/api/campaigns/c1/pitches/send"), ("POST", "/api/gmail/connect"),
])
async def test_a_key_is_refused_everywhere_off_the_allowlist(env, method, path):
    _, key = await approved_key(env)
    r = await env.c.request(method, path, headers={"Authorization": f"Bearer {key}"}, json={})
    assert r.status_code == 403 and "can't use this endpoint" in r.json()["detail"]


async def test_keys_are_never_accepted_in_a_url_and_bad_keys_are_401(env):
    _, key = await approved_key(env)
    assert (await env.c.get(f"/api/gmail?token={key}")).status_code == 401
    assert (await env.c.get("/api/gmail", headers={"Authorization": "Bearer rai_notarealkey"})).status_code == 401


def test_the_allowlist_is_small_and_exact():
    from app.auth.api_key_access import is_allowed

    assert is_allowed("GET", "/api/campaigns/") and is_allowed("GET", "/api/campaigns/c1/leads") and is_allowed("POST", "/api/campaigns/brief-from-url")
    assert not is_allowed("GET", "/api/campaigns/c1/leads/x") and not is_allowed("POST", "/api/campaigns/c1/generate")
    assert not is_allowed("GET", "/api/keys") and not is_allowed("GET", "/api/campaigns/c1/stream")


def test_names_and_codes_are_cleaned():
    assert device.clean_name("  Claude\n Code <b>!</b>  ") == "Claude Code b/b"
    assert device.clean_name("") == "An agent" and len(device.clean_name("x" * 500)) == device.CLIENT_NAME_MAX
    assert device.normalize_user_code("bcdf ghjk") == "BCDF-GHJK" and device.normalize_user_code("BCDF-GH") == ""

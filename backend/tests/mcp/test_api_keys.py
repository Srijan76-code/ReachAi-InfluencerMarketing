import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from app.api.routes import api_keys
from app.auth.user import get_db_user
from app.db.database import get_db
from app.mcp.db import session_scope
from app.models.user import User
from tests.mcp.conftest import rpc

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def web(db):
    """The web-app side: signed in as user u1 (the Clerk login is replaced by an override)."""
    app = FastAPI()
    app.include_router(api_keys.router, prefix="/api/keys")
    current = {"id": "u1"}

    async def fake_user():
        return User(user_id=current["id"], clerk_id="x")

    async def fake_db():
        async with session_scope() as s:
            yield s

    app.dependency_overrides[get_db_user] = fake_user
    app.dependency_overrides[get_db] = fake_db
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        c.as_user = lambda uid: current.update(id=uid)
        yield c


async def test_created_key_is_shown_once_and_works_over_mcp(web, client):
    created = (await web.post("/api/keys", json={"name": "Claude Code"})).json()
    assert created["key"].startswith("rai_") and created["prefix"] == created["key"][:12]
    listed = (await web.get("/api/keys")).json()
    assert [k["name"] for k in listed] == ["Claude Code"]
    assert "key" not in listed[0] and "key_hash" not in listed[0]
    assert (await rpc(client, created["key"], "tools/list")).status_code == 200


async def test_revoking_a_key_stops_it_working(web, client):
    created = (await web.post("/api/keys", json={"name": "temp"})).json()
    assert (await web.delete(f"/api/keys/{created['key_id']}")).status_code == 200
    assert (await web.get("/api/keys")).json() == []
    assert (await rpc(client, created["key"], "tools/list")).status_code == 401


async def test_users_cannot_see_or_revoke_each_others_keys(web):
    created = (await web.post("/api/keys", json={"name": "mine"})).json()
    web.as_user("u2")
    assert (await web.get("/api/keys")).json() == []
    assert (await web.delete(f"/api/keys/{created['key_id']}")).status_code == 404


async def test_key_limit_and_name_validation(web):
    assert (await web.post("/api/keys", json={"name": ""})).status_code == 422
    for i in range(api_keys.MAX_ACTIVE_KEYS):
        assert (await web.post("/api/keys", json={"name": f"k{i}"})).status_code == 201
    assert (await web.post("/api/keys", json={"name": "one too many"})).status_code == 400


async def test_database_stores_only_a_hash(web, db):
    from sqlalchemy import select
    from app.models.api_key import ApiKey

    created = (await web.post("/api/keys", json={"name": "h"})).json()
    async with db() as s:
        row = (await s.execute(select(ApiKey))).scalar_one()
    assert created["key"] not in (row.key_hash, row.prefix) and len(row.key_hash) == 64

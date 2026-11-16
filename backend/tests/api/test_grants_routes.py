"""The founder's side of permissions (F9.8, 8b): read, approve, shorten and remove them on the website. A key is refused
everywhere here: an agent can never approve, widen or restore its own permissions."""

import pytest

from app.agent import grants
from tests.api.test_device_login import approved_key, env  # noqa: F401  (the app, database and sign-in fixture)

pytestmark = pytest.mark.asyncio


async def asked(env, ability="send_replies", mode="unattended", user="u1", campaign="c1"):
    async with env.sf() as db:
        g = await grants.request(db, user, ability=ability, campaign_id=campaign, days=14, mode=mode, per_day=8, client_name="Claude Code")
        return g.user_code


async def test_the_founder_reads_approves_and_removes_a_permission(env):
    code = await asked(env)
    env.as_founder(True)
    seen = (await env.c.get("/api/grants/lookup", params={"code": code.lower()})).json()
    assert seen["label"] == "Send replies and follow-ups" and seen["campaign_name"] == "Mine" and seen["client_name"] == "Claude Code"
    assert "without asking you each time" in seen["what"] and seen["max_days"] == 30 and seen["can_unattended"] is True
    done = (await env.c.post("/api/grants/decision", json={"code": code, "approve": True, "days": 3, "per_day": 2, "mode": "ask"})).json()
    assert done["approved"] is True and done["valid_until"]
    listed = (await env.c.get("/api/grants")).json()["grants"]
    assert len(listed) == 1 and listed[0]["status"] == "approved" and listed[0]["per_day"] == 2 and listed[0]["mode"] == "ask"
    assert (await env.c.delete(f"/api/grants/{listed[0]['id']}")).json() == {"revoked": True}
    assert (await env.c.get("/api/grants")).json()["grants"] == []
    assert (await env.c.post("/api/grants/decision", json={"code": code, "approve": True})).status_code == 404  # decided once


async def test_one_founder_cannot_see_or_decide_anothers_requests(env):
    code = await asked(env, user="u2", campaign="cx")
    env.as_founder(True)  # signed in as u1
    assert (await env.c.get("/api/grants/lookup", params={"code": code})).status_code == 404
    assert (await env.c.post("/api/grants/decision", json={"code": code, "approve": True})).status_code == 404
    assert (await env.c.get("/api/grants")).json()["grants"] == []
    async with env.sf() as db:
        from sqlalchemy import select

        from app.models.agent_grant import AgentGrant

        gid = (await db.execute(select(AgentGrant.grant_id))).scalar_one()
    assert (await env.c.delete(f"/api/grants/{gid}")).status_code == 404


async def test_the_limits_in_a_decision_are_checked(env):
    code = await asked(env)
    env.as_founder(True)
    assert (await env.c.post("/api/grants/decision", json={"code": code, "approve": True, "days": 365})).status_code == 422
    assert (await env.c.post("/api/grants/decision", json={"code": code, "approve": True, "mode": "always"})).status_code == 422
    assert (await env.c.post("/api/grants/decision", json={"code": code, "approve": False})).json()["approved"] is False


async def test_an_agents_key_and_a_signed_out_visitor_are_refused_on_every_permission_endpoint(env):
    code = await asked(env)
    _, key = await approved_key(env)
    h = {"Authorization": f"Bearer {key}"}
    calls = [("GET", "/api/grants", None), ("GET", f"/api/grants/lookup?code={code}", None),
             ("POST", "/api/grants/decision", {"code": code, "approve": True}), ("DELETE", "/api/grants/anything", None)]
    for method, path, body in calls:
        assert (await env.c.request(method, path, headers=h, json=body)).status_code == 403, path
        assert (await env.c.request(method, path, json=body)).status_code == 401, path

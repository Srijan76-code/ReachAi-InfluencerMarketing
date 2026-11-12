import pytest

from tests.mcp.conftest import make_key, rpc

pytestmark = pytest.mark.asyncio


async def test_prompts_are_listed_and_walk_through_the_tools(client, db):
    token = await make_key(db)
    listed = (await rpc(client, token, "prompts/list")).json()["result"]["prompts"]
    assert {p["name"] for p in listed} == {"reachai-new-campaign", "reachai-draft-pitches", "reachai-check-inbox"}
    got = (await rpc(client, token, "prompts/get", {"name": "reachai-new-campaign", "arguments": {"product": "Invoicing app"}})).json()["result"]
    text = got["messages"][0]["content"]["text"]
    assert "Invoicing app" in text and "create_campaign" in text and "confirm=false" in text and "confirm=true" in text
    draft = (await rpc(client, token, "prompts/get", {"name": "reachai-draft-pitches", "arguments": {"campaign_id": "c1", "how_many": "3"}})).json()["result"]
    body = draft["messages"][0]["content"]["text"]
    assert "campaign c1" in body and "pitch_context" in body and "save_draft" in body and "Nothing is sent" in body


async def test_llms_txt_uses_the_configured_address_not_the_request_host(client):
    resp = await client.get("/llms.txt", headers={"Host": "evil.example", "X-Forwarded-Host": "evil.example"})
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/plain")
    text = resp.text
    assert "https://reachai.test/api/mcp" in text and "evil.example" not in text
    assert "https://app.reachai.test/agents" in text and "https://reachai.test/skill.md" in text
    assert '{"mcpServers": {"reachai": {"url": "https://reachai.test/api/mcp"' in text  # braces survive templating
    assert "{MCP_URL}" not in text and "{APP_URL}" not in text and "\x00" not in text


async def test_llms_txt_does_not_ask_for_secrets_in_chat_and_never_contains_a_key(client):
    text = (await client.get("/llms.txt")).text
    assert "Never invent a key" in text and "rai_" not in text


async def test_skill_md_is_a_valid_skill_with_the_safety_rules(client):
    resp = await client.get("/skill.md")
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/markdown")
    text = resp.text
    assert text.startswith("---\nname: reachai\ndescription:")
    for must in ("confirm=false", "nothing is sent", "untrusted", "fair_high_usd", "Never print, log or store"):
        assert must.lower() in text.lower(), must
    assert "{MCP_URL}" not in text and "https://reachai.test/api/mcp" in text


async def test_setup_files_are_public_and_read_only(client):
    assert (await client.post("/llms.txt")).status_code == 405
    assert (await client.get("/skill.md")).status_code == 200  # no sign-in needed

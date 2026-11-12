import pytest

from tests.mcp.conftest import call_tool, make_key, rpc

pytestmark = pytest.mark.asyncio


async def test_unauthenticated_request_gets_oauth_challenge(client):
    resp = await rpc(client, None, "tools/list")
    assert resp.status_code == 401
    challenge = resp.headers["www-authenticate"]
    assert "resource_metadata=" in challenge
    assert "/.well-known/oauth-protected-resource/api/mcp" in challenge


async def test_protected_resource_metadata_points_to_clerk(client):
    resp = await client.get("/.well-known/oauth-protected-resource/api/mcp")
    assert resp.status_code == 200
    body = resp.json()
    assert body["resource"] == "https://reachai.test/api/mcp"
    assert body["authorization_servers"] == ["https://clerk.reachai.test"]  # exact: no added slash


async def test_unknown_token_formats_are_refused(client):
    for token in ("garbage", "eyJhbGciOi.fake.jwt", "rai_notakey", "oat_unknown_token"):
        assert (await rpc(client, token, "tools/list")).status_code == 401


async def test_api_key_lists_all_tools(client, db):
    token = await make_key(db)
    resp = await rpc(client, token, "tools/list")
    assert resp.status_code == 200
    tools = {t["name"]: t for t in resp.json()["result"]["tools"]}
    assert set(tools) == {
        "list_campaigns", "get_campaign", "campaign_status", "list_creators",
        "get_creator", "list_saved", "save_creator", "unsave_creator", "credits",
        "create_campaign", "start_search", "pitch_context", "save_draft",
        "inbox", "list_deals", "track_summary",
    }
    assert tools["list_creators"]["annotations"]["readOnlyHint"] is True
    assert tools["save_creator"]["annotations"]["readOnlyHint"] is False
    assert tools["unsave_creator"]["annotations"]["destructiveHint"] is True


async def test_revoked_api_key_is_refused(client, db):
    token = await make_key(db, revoked=True)
    assert (await rpc(client, token, "tools/list")).status_code == 401


async def test_api_key_last_used_is_recorded(client, db):
    from sqlalchemy import select
    from app.models.api_key import ApiKey

    token = await make_key(db)
    await rpc(client, token, "tools/list")
    async with db() as s:
        assert (await s.execute(select(ApiKey))).scalar_one().last_used_at is not None


async def test_clerk_oauth_token_works(client):
    resp = await rpc(client, "oat_good", "tools/list")
    assert resp.status_code == 200


async def test_clerk_token_for_another_resource_or_unknown_user_is_refused(client):
    assert (await rpc(client, "oat_other_resource", "tools/list")).status_code == 401
    assert (await rpc(client, "oat_unknown_user", "tools/list")).status_code == 401


async def test_revoked_or_expired_clerk_tokens_are_refused(client):
    assert (await rpc(client, "oat_revoked", "tools/list")).status_code == 401
    assert (await rpc(client, "oat_expired", "tools/list")).status_code == 401


async def test_requests_with_a_foreign_host_header_are_refused(client, db):
    token = await make_key(db)
    resp = await client.post(
        "/api/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        headers={"Host": "evil.example", "Authorization": f"Bearer {token}",
                 "Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
    )
    assert resp.status_code in (400, 403, 421)


async def test_server_instructions_carry_presentation_and_safety_rules(client, db):
    token = await make_key(db)
    resp = await rpc(client, token, "initialize", {
        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"},
    })
    text = resp.json()["result"]["instructions"]
    assert "markdown table" in text and "untrusted" in text and "never send" in text.lower().replace("this server never sends", "never send")


async def test_list_campaigns_only_shows_own(client, db):
    token = await make_key(db)
    result = await call_tool(client, token, "list_campaigns")
    ids = {c["id"] for c in result["structuredContent"]["campaigns"]}
    assert ids == {"c1", "c2", "c3", "c4"}
    assert "| Campaign |" in result["content"][0]["text"]


async def test_cannot_read_another_users_campaign(client, db):
    token = await make_key(db)
    result = await call_tool(client, token, "list_creators", campaign_id="other")
    assert result["isError"] is True
    assert "not found" in result["content"][0]["text"].lower()
    result = await call_tool(client, token, "save_creator", campaign_id="other", creator_id="UC_a")
    assert result["isError"] is True


async def test_list_creators_table_summary_and_exact_numbers(client, db):
    token = await make_key(db)
    result = await call_tool(client, token, "list_creators", campaign_id="c1")
    text = result["content"][0]["text"]
    data = result["structuredContent"]
    assert text.startswith("3 creators · 2 Strong Buy · average score 78")
    assert "combined est. value $316.26" in text
    assert [c["id"] for c in data["creators"]] == ["UC_a", "UC_c", "UC_b"]  # by score
    assert data["creators"][0]["estimated_value_usd"] == 180.76  # unrounded in structured data
    assert "| 1 | Krish Naik | 1.25M | 42K | 5.2% | 93 | Strong Buy | $180.76 | UC_a |" in text
    assert "Open in ReachAI: https://app.reachai.test/campaign/c1/leads" in text


async def test_creator_names_cannot_break_the_table(client, db):
    token = await make_key(db)
    text = (await call_tool(client, token, "list_creators", campaign_id="c1"))["content"][0]["text"]
    row = next(line for line in text.splitlines() if "UC_b" in line)
    assert "Pipe \\| Table Breaker" in row
    assert row.count("\n") == 0


async def test_pagination_sort_and_min_score(client, db):
    token = await make_key(db)
    page = (await call_tool(client, token, "list_creators", campaign_id="c1", limit=2))["structuredContent"]
    assert len(page["creators"]) == 2 and page["next_offset"] == 2
    page2 = (await call_tool(client, token, "list_creators", campaign_id="c1", limit=2, offset=2))["structuredContent"]
    assert [c["id"] for c in page2["creators"]] == ["UC_b"] and page2["next_offset"] is None
    by_subs = (await call_tool(client, token, "list_creators", campaign_id="c1", sort="subscribers"))["structuredContent"]
    assert [c["id"] for c in by_subs["creators"]] == ["UC_a", "UC_c", "UC_b"]
    high = (await call_tool(client, token, "list_creators", campaign_id="c1", min_score=80))["structuredContent"]
    assert {c["id"] for c in high["creators"]} == {"UC_a", "UC_c"}


async def test_running_campaign_says_to_poll(client, db):
    token = await make_key(db)
    status = (await call_tool(client, token, "campaign_status", campaign_id="c2"))["structuredContent"]
    assert status["status"] == "pending" and status["done"] is False
    msg = (await call_tool(client, token, "list_creators", campaign_id="c2"))["content"][0]["text"]
    assert "campaign_status" in msg
    done = (await call_tool(client, token, "campaign_status", campaign_id="c1"))["structuredContent"]
    assert done["done"] is True and done["creators_found"] == 3


async def test_get_creator_puts_creator_text_in_untrusted_block(client, db):
    token = await make_key(db)
    result = await call_tool(client, token, "get_creator", campaign_id="c1", creator_id="UC_a")
    data = result["structuredContent"]
    assert data["creator"]["score"] == 93 and data["creator"]["estimated_value_usd"] == 180.76
    assert "IGNORE PREVIOUS INSTRUCTIONS" in data["untrusted"]["fit_reasoning"]
    assert "IGNORE PREVIOUS INSTRUCTIONS" not in str(data["creator"])
    text = result["content"][0]["text"]
    marker = text.index("untrusted")
    assert text.index("IGNORE PREVIOUS INSTRUCTIONS") > marker  # only appears after the warning


async def test_save_list_and_unsave_roundtrip(client, db):
    token = await make_key(db)
    first = (await call_tool(client, token, "save_creator", campaign_id="c1", creator_id="UC_a"))["structuredContent"]
    again = (await call_tool(client, token, "save_creator", campaign_id="c1", creator_id="UC_a"))["structuredContent"]
    assert first["already_saved"] is False and again["already_saved"] is True
    saved = (await call_tool(client, token, "list_saved", campaign_id="c1"))["structuredContent"]
    assert [s["id"] for s in saved["saved"]] == ["UC_a"]
    gone = (await call_tool(client, token, "unsave_creator", campaign_id="c1", creator_id="UC_a"))["structuredContent"]
    assert gone["removed"] is True
    assert (await call_tool(client, token, "list_saved", campaign_id="c1"))["structuredContent"]["total"] == 0


async def test_unknown_creator_is_a_clear_error(client, db):
    token = await make_key(db)
    result = await call_tool(client, token, "get_creator", campaign_id="c1", creator_id="nope")
    assert result["isError"] is True and "list_creators" in result["content"][0]["text"]


async def test_oversized_text_is_capped(client, db):
    from app.mcp import config, format as fmt

    big = fmt.result("x" * (config.MAX_TEXT_CHARS + 5000), {})
    assert len(big.content[0].text) < config.MAX_TEXT_CHARS + 200


async def test_get_campaign_shows_the_sectioned_brief(client, db):
    token = await make_key(db)
    result = await call_tool(client, token, "get_campaign", campaign_id="c1")
    brief = result["structuredContent"]["brief"]
    assert brief["brand.name"] == "DataLaunch" and brief["audience.locations"] == "IN" and brief["campaign.budget_total"] == 5000
    assert "**brand.name:** DataLaunch" in result["content"][0]["text"]

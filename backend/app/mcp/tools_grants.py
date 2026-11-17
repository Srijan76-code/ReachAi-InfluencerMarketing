"""request_permission and my_permissions: how the founder's agent asks for more (F9.8, 8b).

The agent can only ask. The founder reads the request on the website, can make it shorter or stricter, and approves once;
the agent then works inside it until it ends or is removed. Nothing here can approve, widen or restore a permission."""

from __future__ import annotations

from typing import Annotated, Literal, Optional

from fastapi import HTTPException
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, ToolAnnotations
from pydantic import Field

from app.agent import grants
from app.mcp import format as fmt
from app.mcp.auth import current_user_id
from app.mcp.config import app_url
from app.mcp.db import session_scope
from app.mcp.tools import CampaignId

ASKS = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)
READS = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)


def register_grant_tools(server: MCPServer) -> None:
    @server.tool(
        title="Ask the founder for a permission",
        description=(
            "Ask the founder to let you do more in ONE campaign. You get a link and a short code: give them the link and "
            "tell them to open it, read what it allows, and approve. You can't approve it yourself, and it does nothing "
            "until they do. Abilities: write_replies (write replies and follow-ups), send_replies (send them from their "
            "Gmail), send_first_emails (send first emails), autopilot (turn ReachAI's autopilot on or off), manage_campaign "
            "(add creators to deals, set up Track). For the sending abilities, mode 'ask' means they say yes in chat each "
            "time (the default); 'unattended' lets you send inside the limits without asking each time: only ask for it if "
            "they told you to run unattended. Check my_permissions afterwards."
        ),
        annotations=ASKS,
    )
    async def request_permission(
        campaign_id: CampaignId,
        ability: Annotated[Literal["write_replies", "send_replies", "send_first_emails", "autopilot", "manage_campaign"], Field(description="What you need to do.")],
        days: Annotated[int, Field(ge=1, le=grants.MAX_DAYS, description="How long it should last (the founder can shorten it).")] = grants.DEFAULT_DAYS,
        mode: Annotated[Literal["ask", "unattended"], Field(description="Sending only: ask = a yes in chat each time; unattended = within the limits, no asking.")] = "ask",
        per_day: Annotated[Optional[int], Field(ge=1, le=20, description="Sending only: most messages a day.")] = None,
        client_name: Annotated[Optional[str], Field(max_length=60, description="What you are called, e.g. 'Claude Code'.")] = None,
    ) -> CallToolResult:
        user_id = current_user_id()
        async with session_scope() as db:
            try:
                g = await grants.request(db, user_id, ability=ability, campaign_id=campaign_id, days=days, mode=mode,
                                         per_day=per_day, client_name=client_name)
            except HTTPException as exc:
                raise ToolError(str(exc.detail))
            what = grants.describe(g)
        url = f"{app_url()}/grant?code={g.user_code}"
        text = (f"Asked. Give the founder this link and tell them to open it, check the code {g.user_code} and approve: {url}\n\n"
                f"They'll read: \"{what}\" for up to {g.requested_days} days. They can shorten it or make it stricter. "
                f"The request lapses in {grants.REQUEST_TTL_MINUTES} minutes. Nothing changes until they approve; check my_permissions.")
        return fmt.result(text, {"grant_id": g.grant_id, "ability": ability, "campaign_id": campaign_id, "user_code": g.user_code,
                                 "approval_url": url, "what_it_allows": what, "expires_in_minutes": grants.REQUEST_TTL_MINUTES})

    @server.tool(
        title="My permissions",
        description="What the founder has allowed you, what is waiting for their approval, and when each ends.",
        annotations=READS,
    )
    async def my_permissions() -> CallToolResult:
        user_id = current_user_id()
        async with session_scope() as db:
            rows = await grants.listing(db, user_id)
        if not rows:
            return fmt.result("Nothing is allowed yet beyond reading and drafting. Use request_permission.", {"permissions": []})
        lines = [f"- **{r['label']}** in {fmt.cell(r['campaign_name'] or r['campaign_id'], 40)}: "
                 + (f"waiting for the founder (code {r['user_code']})" if r["status"] == "pending"
                    else f"allowed until {r['valid_until'][:10]}" + (f", {r['mode']}" if r["can_unattended"] else ""))
                 for r in rows]
        return fmt.result("\n".join(lines), {"permissions": [{k: v for k, v in r.items() if k != "what"} for r in rows]})

"""add_to_deals, set_autopilot, track_setup, track_snippet: running a campaign from an agent (F9.8, 8c).

Each tool calls the same handler the website calls, so there is one set of rules, and each needs the founder's permission
for that campaign (request_permission). Sending first emails is send_message with the send_first_emails permission."""

from __future__ import annotations

import logging
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
from app.mcp.tools import CampaignId, _owned_campaign
from app.models.user import User

logger = logging.getLogger(__name__)

WRITES = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
CHANGES = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)


async def need(db, user_id: str, campaign_id: str, ability: str):
    """The permission for this campaign, or a ToolError that tells the agent how to ask for it."""
    g = await grants.active(db, user_id, ability, campaign_id)
    if g is None:
        raise ToolError(f"This needs the founder's permission ('{ability}') for this campaign. Call request_permission with "
                        f"ability '{ability}' and give them the link; then check my_permissions.")
    return g


def _detail(exc: HTTPException) -> str:
    d = exc.detail
    return d if isinstance(d, str) else str(d)


def register_manage_tools(server: MCPServer) -> None:
    @server.tool(
        title="Add creators to deals",
        description=(
            "Put creators from a campaign's results into its Outreach tab (a chat for each), so you can save first messages "
            "for them (save_draft) and track the conversation (list_deals, inbox). Creators already there are skipped. "
            "Needs the founder's permission 'manage_campaign' for the campaign. Nothing is sent."
        ),
        annotations=WRITES,
    )
    async def add_to_deals(
        campaign_id: CampaignId,
        creator_ids: Annotated[list[str], Field(min_length=1, max_length=50, description="Creator ids from list_creators.")],
    ) -> CallToolResult:
        from app.api.routes.deals import NewDeals, add_deals

        user_id = current_user_id()
        async with session_scope() as db:
            campaign = await _owned_campaign(db, campaign_id, user_id)
            await need(db, user_id, campaign_id, "manage_campaign")
            known = {str(l.get("id")) for l in (campaign.campaign_leads or []) if isinstance(l, dict)}
            unknown = [c for c in dict.fromkeys(creator_ids) if c not in known]
            user = await db.get(User, user_id)
            try:
                out = await add_deals(campaign_id, NewDeals(creator_ids=creator_ids), user, db)
            except HTTPException as exc:
                raise ToolError(_detail(exc))
        n = len(out["created"])
        text = (f"Added {n} creator{'s' if n != 1 else ''} to Outreach" + (f"; {out['skipped']} were already there" if out["skipped"] else "")
                + (f"; not in this campaign's results: {', '.join(unknown)}" if unknown else "")
                + f".\nNext: pitch_context and save_draft for each, then ask the founder to review (or request_permission 'send_first_emails').\n"
                f"Open in ReachAI: {fmt.campaign_link(campaign_id, 'outreach')}")
        return fmt.result(text, {"created": [{"deal_id": d["id"], "creator_id": d.get("creator_id")} for d in out["created"]], "skipped": out["skipped"],
                                 "not_in_campaign": unknown})

    @server.tool(
        title="Set autopilot",
        description=(
            "Turn ReachAI's autopilot on or off for a campaign. With autopilot on, ReachAI itself sends the first emails and "
            "follow-ups drafted for the campaign, spaced out, from the founder's Gmail, and stops for them at decisions. "
            "Needs the founder's permission 'autopilot'. 'review_first' makes first emails wait for the founder."
        ),
        annotations=CHANGES,
    )
    async def set_autopilot(
        campaign_id: CampaignId,
        on: Annotated[bool, Field(description="True to turn autopilot on, false to turn it off.")],
        review_first: Annotated[bool, Field(description="Keep first emails waiting for the founder's check.")] = True,
    ) -> CallToolResult:
        from app.api.routes.deals import AutopilotIn
        from app.api.routes.deals import set_autopilot as set_autopilot_route

        user_id = current_user_id()
        async with session_scope() as db:
            await _owned_campaign(db, campaign_id, user_id)
            await need(db, user_id, campaign_id, "autopilot")
            user = await db.get(User, user_id)
            try:
                out = await set_autopilot_route(campaign_id, AutopilotIn(autopilot=on, review_first=review_first), user, db)
            except HTTPException as exc:
                raise ToolError(_detail(exc))
        return fmt.result(f"Autopilot is {'on' if on else 'off'}" + (" (first emails wait for the founder)" if on and review_first else "") + ".",
                          {"autopilot": out["autopilot"], "review_first": out["review_first"]})

    @server.tool(
        title="Set the Track goal",
        description=(
            "Set what the campaign is trying to get (signups or sales, how many, and what each is worth) so Track can show "
            "progress and cost per result. Needs the founder's permission 'manage_campaign'."
        ),
        annotations=WRITES,
    )
    async def track_setup(
        campaign_id: CampaignId,
        goal_kind: Annotated[Literal["signups", "sales"], Field(description="What counts as a result.")],
        goal_count: Annotated[Optional[int], Field(ge=1, le=100_000_000, description="How many results you are aiming for.")] = None,
        value_each: Annotated[Optional[float], Field(ge=0, le=1_000_000, description="What one result is worth, in dollars.")] = None,
    ) -> CallToolResult:
        from app.api.routes.track import GoalIn, set_goal

        user_id = current_user_id()
        async with session_scope() as db:
            await _owned_campaign(db, campaign_id, user_id)
            await need(db, user_id, campaign_id, "manage_campaign")
            user = await db.get(User, user_id)
            body = GoalIn(goal_kind=goal_kind, **({"goal_count": goal_count} if goal_count else {}), **({"value_each": value_each} if value_each is not None else {}))
            try:
                out = await set_goal(campaign_id, body, user, db)
            except HTTPException as exc:
                raise ToolError(_detail(exc))
        return fmt.result(f"Track goal saved: {goal_kind}" + (f", {goal_count:,}" if goal_count else "") + ".", out)

    @server.tool(
        title="Track signup snippet",
        description=(
            "The one-line snippet that counts signups from creators' links on the founder's site, the exact steps, and whether "
            "it has been seen yet. The founder (or you, if you can edit their site) adds it; then open the site with "
            "?reachai_test=1 to confirm. Needs the founder's permission 'manage_campaign'."
        ),
        annotations=WRITES,
    )
    async def track_snippet(campaign_id: CampaignId) -> CallToolResult:
        from app.api.routes.track import _ensure_key, _track

        user_id = current_user_id()
        async with session_scope() as db:
            campaign = await _owned_campaign(db, campaign_id, user_id)
            await need(db, user_id, campaign_id, "manage_campaign")
            key = await _ensure_key(db, campaign)
            campaign = await _owned_campaign(db, campaign_id, user_id)
            seen = _track(campaign.campaign_details).get("snippet_seen_at")
        base = app_url()
        tag = f'<script src="{base}/t.js" data-key="{key}" async></script>'
        text = (f"Add this to every page of the founder's site (before </body>):\n\n    {tag}\n\n"
                'On the page shown after a signup, either add the attribute `data-signup` to that tag on that page, or call '
                '`window.reachai("signup")` (`"sale"` for a purchase). It sends only the creator\'s code, no personal data.\n'
                f"To confirm, open the site once with ?reachai_test=1. Seen so far: {seen or 'not yet'}.")
        return fmt.result(text, {"snippet": tag, "key": key, "script": f"{base}/t.js", "endpoint": f"{base}/api/t/{key}", "seen_at": seen})

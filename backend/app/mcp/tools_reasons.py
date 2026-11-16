"""submit_reasons: the founder's own agent words the "Why this creator" bullets and ReachAI checks them (F9.6).

The agent writes (its own AI, no cost to ReachAI). The server runs the same code rules and Jev rubric as for our own
AI's bullets and replies with what to fix. After the allowed tries the plain checked facts stay, so the founder
never sees an unchecked sentence."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, ToolAnnotations
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.billing.costs import CostContext
from app.discovery import agent_ai
from app.judge import constants as K
from app.mcp import format as fmt
from app.mcp.auth import current_user_id
from app.mcp.db import session_scope
from app.mcp.tools import CampaignId, _leads, _owned_campaign
from app.models.campaign import Campaign

logger = logging.getLogger(__name__)

WRITES = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
MAX_ITEMS = 10


class ReasonItem(BaseModel):
    creator_id: str = Field(description="The creator's id from list_creators.")
    bullets: list[str] = Field(min_length=3, max_length=3, description="Exactly 3 plain sentences: why them, watch out (or another strength), when to choose them.")


async def _check_one(campaign: Campaign, item: ReasonItem, user_id: str) -> dict[str, Any]:
    from app.judge import client as jev

    lead = next((l for l in _leads(campaign) if str(l.get("id")) == item.creator_id), None)
    base = {"creator_id": item.creator_id}
    if lead is None:
        return {**base, "status": "not_found", "message": "Creator not found in this campaign. Use list_creators for the ids."}
    facts = lead.get("reason_facts")
    if not facts:
        return {**base, "status": "not_applicable",
                "message": "ReachAI's own AI already wrote this creator's text (the search was not started by an agent). Nothing to do."}
    if lead.get("reason_source") == "agent":
        return {**base, "status": "already_written", "message": "These bullets were already written and checked. Nothing to do."}
    tries = int(lead.get("reason_attempts") or 0)
    if tries >= K.AGENT_REASON_ATTEMPTS:
        return {**base, "status": "facts_kept", "message": "The tries are used up, so the plain checked facts stay. Move on to the next creator."}

    async def judge(state, questions):
        return await jev.judge(state, questions, context=CostContext(user_id=user_id, campaign_id=campaign.campaign_id))

    try:
        r = await agent_ai.review_bullets(facts["points"], facts.get("verdict"), item.bullets, judge)
    except jev.JudgeUnavailableError:
        return {**base, "status": "check_unavailable", "message": "The checker is busy. Nothing was saved and no try was used: send the same bullets again in a minute."}
    if r["stop"]:
        return {**base, "status": "stopped", "message": "These facts can't be reworded safely. The plain facts stay."}
    return {**base, "result": r, "tries_before": tries}


async def _save(campaign_id: str, user_id: str, outcomes: list[dict]) -> None:
    """Write passes and counted failures into the campaign's leads, re-reading them under a row lock."""
    async with session_scope() as db:
        campaign = (await db.execute(select(Campaign).where(Campaign.campaign_id == campaign_id, Campaign.user_id == user_id)
                                     .with_for_update())).scalar_one()
        leads = list(campaign.campaign_leads or [])
        by_id = {str(l.get("id")): i for i, l in enumerate(leads)}
        for o in outcomes:
            if "result" not in o or o["creator_id"] not in by_id:
                continue
            lead = dict(leads[by_id[o["creator_id"]]])
            tries = int(lead.get("reason_attempts") or 0) + 1
            lead["reason_attempts"] = tries
            if o["result"]["passed"]:
                bullets = o["result"]["bullets"]
                lead.update(reason_points=bullets, llm_reasoning=" ".join(bullets), reason_source="agent")
            leads[by_id[o["creator_id"]]] = lead
        campaign.campaign_leads = leads  # reassign so the JSON change is saved
        await db.commit()


def register_reason_tools(server: MCPServer) -> None:
    @server.tool(
        title="Submit 'why this creator' bullets",
        description=(
            "Send the 3 bullets YOU wrote for up to 10 creators; ReachAI checks them against the facts it computed "
            "(nothing invented, agrees with the verdict, the second bullet is the right kind) and replies per creator "
            "with passed or what to fix. Rewrite what failed and send it again. Each creator gets 3 tries, then the "
            "plain checked facts stay. Get the facts, the prompt and the writing rules from get_creator "
            "(`write_why`). Only needed for searches you started."
        ),
        annotations=WRITES,
    )
    async def submit_reasons(
        campaign_id: CampaignId,
        items: Annotated[list[ReasonItem], Field(min_length=1, max_length=MAX_ITEMS, description="One entry per creator.")],
    ) -> CallToolResult:
        user_id = current_user_id()
        async with session_scope() as db:
            campaign = await _owned_campaign(db, campaign_id, user_id)
        if len({i.creator_id for i in items}) != len(items):
            raise ToolError("Send each creator once per call.")
        outcomes = await asyncio.gather(*[_check_one(campaign, i, user_id) for i in items])
        await _save(campaign_id, user_id, list(outcomes))
        results, lines = [], []
        for o in outcomes:
            if "result" not in o:
                results.append({k: v for k, v in o.items() if k != "tries_before"})
                lines.append(f"- {o['creator_id']}: {o['message']}")
                continue
            r, left = o["result"], K.AGENT_REASON_ATTEMPTS - (o["tries_before"] + 1)
            if r["passed"]:
                status, msg = "passed", "Saved. It now shows in the app and in get_creator."
            elif left <= 0:
                status, msg = "facts_kept", "Still not right and the tries are used up, so the plain checked facts stay. Move on."
            else:
                status, msg = "rewrite", f"Rewrite and send again ({left} {'try' if left == 1 else 'tries'} left)."
            results.append({"creator_id": o["creator_id"], "status": status, "message": msg, "passed": r["passed"],
                            "fix_these": r["fix_these"], "what_was_right": r["what_was_right"], "tries_left": max(left, 0)})
            detail = "" if r["passed"] else " Fix: " + "; ".join(f"{p.get('check')}" + (f" (bullet {p['bullet']})" if p.get("bullet") else "") for p in r["fix_these"])
            lines.append(f"- {o['creator_id']}: {status}. {msg}{detail}")
        return fmt.result("\n".join(lines), {"results": results})

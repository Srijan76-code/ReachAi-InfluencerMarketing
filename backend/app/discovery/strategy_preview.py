"""The strategy preview on the brief page (F1.24b): the founder sees what ReachAI will search for before spending credits, and
can change it. The strategy is made with the same prompt and route as the real search and stored under the same brief hash, so
when the brief hasn't changed the search reuses it and the preview costs nothing extra. An edit is checked by code (the same
rules an agent's strategy gets) and rides along as `campaign.chosen_strategy`."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select

from app.billing.costs import CostContext
from app.discovery import agent_ai
from app.discovery.brief import Brief
from app.discovery.prompts import STRATEGY_PROMPT_VERSION, StrategyOut, strategy_prompt
from app.llm.client import LLMUnavailableError, achat
from app.models.cost_event import CostEvent
from app.models.discovery_run import RunStrategy

PREVIEWS_PER_DAY = 30  # fresh strategies a founder can preview a day (each is one small AI call; repeats are free)


def brief_key(brief: Brief) -> str:
    """The key the search node looks the strategy up by (so a preview is reused by the search)."""
    return f"{STRATEGY_PROMPT_VERSION}:{brief.hash()}"


async def previews_today(db, user_id: str) -> int:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return (await db.scalar(select(func.count()).select_from(CostEvent).where(
        CostEvent.user_id == user_id, CostEvent.route == "strategy", CostEvent.run_id.is_(None), CostEvent.created_at >= start))) or 0


async def preview(db, brief: Brief, user_id: str) -> tuple[dict, bool]:
    """(the strategy as the search would use it, whether it was already made for this exact brief)."""
    key = brief_key(brief)
    found = (await db.execute(select(RunStrategy).where(RunStrategy.brief_hash == key).order_by(RunStrategy.created_at.desc()).limit(1))).scalar_one_or_none()
    if found is not None:
        return found.strategy, True
    if await previews_today(db, user_id) >= PREVIEWS_PER_DAY:
        raise HTTPException(429, f"You've previewed {PREVIEWS_PER_DAY} searches today. Start the search, or try again tomorrow.")
    try:
        result = await achat("strategy", strategy_prompt(brief), StrategyOut, context=CostContext(user_id=user_id))
    except LLMUnavailableError:
        raise HTTPException(503, "We couldn't prepare the preview right now. You can still start the search.")
    out = result.model_dump() if hasattr(result, "model_dump") else dict(result)
    db.add(RunStrategy(run_id=f"preview-{uuid.uuid4()}", campaign_id=None, brief_hash=key, strategy=out))
    await db.commit()
    return out, False


def check_chosen(brief: Brief) -> Optional[dict]:
    """The founder's edited strategy, cleaned, or None when there is none. Raises 422 saying what to change."""
    if not brief.chosen_strategy:
        return None
    cleaned, problems = agent_ai.clean(brief.chosen_strategy, brief)
    if problems:
        raise HTTPException(422, "Your search needs changes: " + "; ".join(str(p.get("check")) for p in problems[:4]) + ".")
    return cleaned

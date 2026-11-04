"""Campaign run status helpers used by the API. Runs themselves live in app/discovery/runtime.py."""

from typing import Optional

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.errors import UndefinedTable
from sqlalchemy import select

from app.core.config import LANGGRAPH_CHECKPOINTER_URL
from app.db.database import AsyncSessionLocal
from app.models.campaign import Campaign


async def get_current_stage(campaign_id: str):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Campaign).where(Campaign.campaign_id == campaign_id)
        )
        campaign = result.scalar_one_or_none()
        if not campaign:
            return None
        return campaign.workflow_status or {
            "status": campaign.status.value if hasattr(campaign.status, "value") else str(campaign.status),
            "stage": None,
        }


async def get_durable_checkpoint_status(thread_id: Optional[str]):
    if not thread_id:
        return {"checkpointed": False, "checkpoint_id": None}

    try:
        async with AsyncPostgresSaver.from_conn_string(
            LANGGRAPH_CHECKPOINTER_URL
        ) as checkpointer:
            checkpoint = await checkpointer.aget_tuple(
                {"configurable": {"thread_id": thread_id}}
            )
            return {
                "checkpointed": checkpoint is not None,
                "checkpoint_id": (
                    checkpoint.config["configurable"].get("checkpoint_id")
                    if checkpoint
                    else None
                ),
            }
    except UndefinedTable:
        return {"checkpointed": False, "checkpoint_id": None}

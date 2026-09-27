import asyncio
import logging
import time
from typing import Any, Dict, Optional

import inngest
from inngest.experimental.realtime import publish as publish_realtime
from langgraph.cache.memory import InMemoryCache
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.errors import UndefinedTable
from sqlalchemy import select, update

from app.core.config import LANGGRAPH_CHECKPOINTER_URL
from app.db.database import AsyncSessionLocal
from app.inngest.client import inngest_client
from app.models.campaign import Campaign, CampaignStatus

logger = logging.getLogger(__name__)


def _normalize_event_name(event: Dict[str, Any]) -> Optional[str]:
    if not isinstance(event, dict):
        return None

    if event.get("event") != "on_chain_start":
        return None

    metadata = event.get("metadata") or {}
    stage_name = metadata.get("langgraph_node")
    if stage_name:
        return str(stage_name)

    name = event.get("name")
    if name and name != "LangGraph":
        return str(name)

    return None


async def publish_stage_update(run_id: str, thread_id: str, stage_name: Optional[str], *, status: str = "running") -> None:
    if not stage_name:
        return

    try:
        await publish_realtime(
            inngest_client,
            channel=f"campaign:{run_id}",
            topic="status",
            data={
                "run_id": run_id,
                "thread_id": thread_id,
                "stage": stage_name,
                "status": status,
                "ts": int(time.time() * 1000),
            },
        )
    except Exception:
        logger.exception("Failed to publish stage update for %s/%s", run_id, thread_id)


async def run_graph_with_stage_events(
    campaign_id: str,
    run_id: str,
    thread_id: str,
    campaign_details: Dict[str, Any],
    user_id: str,
):
    async with AsyncSessionLocal() as db:
        config = {"configurable": {"thread_id": thread_id}}
        try:
            from app.my_agent.agent import graph

            async with AsyncPostgresSaver.from_conn_string(LANGGRAPH_CHECKPOINTER_URL) as checkpointer:
                await checkpointer.setup()
                workflow = graph.compile(checkpointer=checkpointer, cache=InMemoryCache())

                async for event in workflow.astream_events(
                    campaign_details,
                    config=config,
                    version="v2",
                ):
                    stage_name = _normalize_event_name(event)
                    if stage_name:
                        await publish_stage_update(run_id, thread_id, stage_name)
                        await db.execute(
                            update(Campaign)
                            .where(Campaign.campaign_id == campaign_id)
                            .values(
                                workflow_status={
                                    "run_id": run_id,
                                    "thread_id": thread_id,
                                    "stage": stage_name,
                                    "status": "running",
                                }
                            )
                        )
                        await db.commit()

                state = await workflow.aget_state(config)
                final_value = state.values if hasattr(state, "values") else {}
                results = final_value.get("final_ranked_leads") or []

                await db.execute(
                    update(Campaign)
                    .where(Campaign.campaign_id == campaign_id)
                    .values(
                        campaign_leads=results,
                        status=CampaignStatus.COMPLETED,
                        workflow_status={
                            "run_id": run_id,
                            "thread_id": thread_id,
                            "stage": "completed",
                            "status": "completed",
                        },
                    )
                )
                await db.commit()

            await publish_stage_update(run_id, thread_id, "completed", status="completed")
            return {"success": True, "campaign_id": campaign_id, "run_id": run_id, "thread_id": thread_id}

        except Exception:
            logger.exception("Campaign %s failed while running workflow", campaign_id)
            await db.execute(
                update(Campaign)
                .where(Campaign.campaign_id == campaign_id)
                .values(
                    status=CampaignStatus.CREATED,
                    workflow_status={
                        "run_id": run_id,
                        "thread_id": thread_id,
                        "stage": "failed",
                        "status": "failed",
                    },
                )
            )
            await db.commit()
            await publish_stage_update(run_id, thread_id, "failed", status="failed")
            raise


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

import logging
import uuid

import inngest
from sqlalchemy import update

from app.db.database import AsyncSessionLocal
from app.inngest.client import inngest_client
from app.models.campaign import Campaign, CampaignStatus
from app.workflow.runtime import run_graph_with_stage_events

logger = logging.getLogger(__name__)


@inngest_client.create_function(
    fn_id="run_campaign",
    trigger=inngest.TriggerEvent(event="campaign/run"),
)
async def run_campaign(ctx: inngest.Context):
    campaign_id = ctx.event.data["campaign_id"]
    campaign_details = ctx.event.data["campaign_details"]
    user_id = ctx.event.data.get("user_id")
    thread_id = ctx.event.data.get("thread_id") or str(uuid.uuid4())
    run_id = ctx.event.data["run_id"]

    async with AsyncSessionLocal() as db:
        try:
            logger.info("[Inngest] Starting campaign run %s with thread_id=%s", campaign_id, thread_id)

            await db.execute(
                update(Campaign)
                .where(Campaign.campaign_id == campaign_id)
                .values(
                    run_id=run_id,
                    thread_id=thread_id,
                    status=CampaignStatus.PENDING,
                    workflow_status={
                        "run_id": run_id,
                        "thread_id": thread_id,
                        "stage": "queued",
                        "status": "running",
                    },
                )
            )
            await db.commit()

            result = await run_graph_with_stage_events(
                campaign_id=campaign_id,
                run_id=run_id,
                thread_id=thread_id,
                campaign_details=campaign_details,
                user_id=user_id,
            )

            logger.info("[Inngest] Completed campaign %s with run_id=%s thread_id=%s", campaign_id, run_id, thread_id)
            return result

        except Exception as exc:
            logger.exception("[Inngest] Campaign %s failed during workflow execution", campaign_id)
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
                        "error": str(exc),
                    },
                )
            )
            await db.commit()
            raise

import logging
import uuid

import inngest
from sqlalchemy import update

from app.db.database import AsyncSessionLocal
from app.inngest.client import inngest_client
from app.models.campaign import Campaign, CampaignStatus
from app.workflow.runtime import run_graph_with_stage_events
from app.outreach.runtime import run_outreach_graph

logger = logging.getLogger(__name__)

STAGES = [
    {"stage": "campaign_understanding", "message": "Analyzing campaign brief & defining target persona..."},
    {"stage": "keyword_generator", "message": "Generating high-intent search keywords & niche queries..."},
    {"stage": "youtube_search_gate", "message": "Searching YouTube & querying prospective creators..."},
    {"stage": "subscriber_filter", "message": "Filtering channels by subscriber and view thresholds..."},
    {"stage": "channel_enrichment", "message": "Enriching channel profiles & extracting performance metrics..."},
    {"stage": "semantic_processor", "message": "Processing video semantics & audience fit..."},
    {"stage": "reranker_node", "message": "Reranking top creator candidates with AI reasoning..."},
    {"stage": "final_scoring_node", "message": "Calculating final scores, ROI forecast & fair valuations..."},
    {"stage": "llm_reasoning_node", "message": "Synthesizing comprehensive lead dossiers & outreach pitch..."},
]

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


@inngest_client.create_function(
    fn_id="run_outreach",
    trigger=inngest.TriggerEvent(event="outreach/run"),
)
async def run_outreach(ctx: inngest.Context):
    data = ctx.event.data
    return await run_outreach_graph(
        outreach_job_id=data["outreach_job_id"],
        run_id=data["run_id"],
        thread_id=data["thread_id"],
    )

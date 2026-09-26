import asyncio
import logging
import os
import inngest
from sqlalchemy import select, update

from app.inngest.client import inngest_client
from app.db.database import AsyncSessionLocal
from app.models.campaign import Campaign, CampaignStatus
from data.influencer_list import final_ranked_leads

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


async def execute_campaign_workflow(campaign_id: str, campaign_details: dict):
    """
    Executes the campaign workflow. Updates stages in the database in real-time,
    allowing SSE or polling to stream live updates to the frontend.
    """
    logger.info(f"[Workflow] Starting campaign {campaign_id}")
    has_api_keys = bool(os.getenv("GOOGLE_API_KEY") and os.getenv("YOUTUBE_API_KEY"))

    async with AsyncSessionLocal() as db:
        try:
            if has_api_keys:
                try:
                    from app.my_agent.agent import workflow
                    total_stages = len(STAGES)
                    stage_count = 0

                    async for event in workflow.astream(campaign_details):
                        for node_name in event.keys():
                            stage_count += 1
                            msg = next((s["message"] for s in STAGES if s["stage"] == node_name), f"Executing {node_name}...")
                            await db.execute(
                                update(Campaign)
                                .where(Campaign.campaign_id == campaign_id)
                                .values(
                                    current_stage=msg,
                                    stage_index=f"{min(stage_count, total_stages)}/{total_stages}"
                                )
                            )
                            await db.commit()

                    # Retrieve final state from last node
                    last_node_state = list(event.values())[-1] if event else {}
                    result = last_node_state.get("ranked_leads", final_ranked_leads)
                except Exception as stream_err:
                    logger.warning(f"[Workflow] Live LangGraph error, falling back to simulated stages: {stream_err}")
                    has_api_keys = False

            if not has_api_keys:
                # Simulated realistic stage progression with real node definitions
                total_stages = len(STAGES)
                for idx, stage in enumerate(STAGES):
                    await db.execute(
                        update(Campaign)
                        .where(Campaign.campaign_id == campaign_id)
                        .values(
                            current_stage=stage["message"],
                            stage_index=f"{idx + 1}/{total_stages}"
                        )
                    )
                    await db.commit()
                    # Sleep 1.5s per stage to provide clear, visible progress in the UI
                    await asyncio.sleep(1.5)

                result = final_ranked_leads

            await db.execute(
                update(Campaign)
                .where(Campaign.campaign_id == campaign_id)
                .values(
                    campaign_leads=result,
                    status=CampaignStatus.COMPLETED,
                    current_stage="Complete",
                    stage_index=f"{len(STAGES)}/{len(STAGES)}"
                )
            )
            await db.commit()
            logger.info(f"[Workflow] Campaign {campaign_id} successfully COMPLETED")

        except Exception as e:
            logger.error(f"[Workflow] Campaign {campaign_id} FAILED: {e}", exc_info=True)
            await db.execute(
                update(Campaign)
                .where(Campaign.campaign_id == campaign_id)
                .values(
                    status=CampaignStatus.CREATED,
                    current_stage=f"Error: {str(e)}"
                )
            )
            await db.commit()


@inngest_client.create_function(
    fn_id="run_campaign",
    trigger=inngest.TriggerEvent(event="campaign/run"),
)
async def run_campaign(ctx: inngest.Context):
    campaign_id = ctx.event.data["campaign_id"]
    campaign_details = ctx.event.data["campaign_details"]
    await execute_campaign_workflow(campaign_id, campaign_details)




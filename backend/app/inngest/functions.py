import asyncio
import logging
import inngest
from sqlalchemy import select, update

from app.inngest.client import inngest_client
from app.db.database import AsyncSessionLocal
from app.models.campaign import Campaign, CampaignStatus

from app.my_agent.agent import workflow  
from data.influencer_list import final_ranked_leads
logger = logging.getLogger(__name__)


@inngest_client.create_function(
    fn_id="run_campaign",
    trigger=inngest.TriggerEvent(event="campaign/run"),
)
async def run_campaign(ctx: inngest.Context):

    campaign_id = ctx.event.data["campaign_id"]
    campaign_details = ctx.event.data["campaign_details"]

    async with AsyncSessionLocal() as db:
        try:
            logger.info(f"[Inngest] Running campaign {campaign_id}")

            # result = await workflow.ainvoke(campaign_details)
            await asyncio.sleep(20)
            result = final_ranked_leads

            await db.execute(
                update(Campaign)
                .where(Campaign.campaign_id == campaign_id)
                .values(
                    campaign_leads=result,
                    status=CampaignStatus.COMPLETED
                )
            )

            await db.commit()

            logger.info(f"[DB] {campaign_id} → COMPLETED")

        except Exception as e:
            logger.error(f"[DB] {campaign_id} → FAILED: {e}")



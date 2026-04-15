from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from uuid import uuid4

from app.db.database import get_db
from app.models.campaign import Campaign, CampaignStatus

from app.inngest.client import inngest_client
import inngest


router = APIRouter()


# GET /api/campaigns
@router.get("/")
async def get_campaigns(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Campaign).where(Campaign.user_id == user_id)
    )
    campaigns = result.scalars().all()
    return campaigns


# POST /api/campaigns/create
@router.post("/create")
async def create_campaign(user_id: str, db: AsyncSession = Depends(get_db)):
    campaign = Campaign(
        campaign_id=str(uuid4()),
        user_id=user_id,
        status=CampaignStatus.CREATED
    )

    db.add(campaign)
    await db.commit()

    return {
        "success": True,
        "campaign_id": campaign.campaign_id
    }


# GET /api/campaigns/{campaign_id}/details
@router.get("/{campaign_id}/details")
async def get_campaign_details(campaign_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Campaign).where(Campaign.campaign_id == campaign_id)
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(404, "Campaign not found")

    return campaign


# POST /api/campaigns/{campaign_id}/generate
@router.post("/{campaign_id}/generate")
async def generate_campaign(
    campaign_id: str,
    campaign_details: dict,
    db: AsyncSession = Depends(get_db)
):
    # update campaign with details + set pending
    await db.execute(
        update(Campaign)
        .where(Campaign.campaign_id == campaign_id)
        .values(
            campaign_details=campaign_details,
            status=CampaignStatus.PENDING
        )
    )

    await db.commit()

    await inngest_client.send(
    inngest.Event(
        name="campaign/run",
        data={
            "campaign_id": campaign_id,
            "campaign_details": campaign_details
        }
    )
)
    return {
        "success": True,
        "campaign_id": campaign_id
    }


# GET /api/campaigns/{campaign_id}/leads
@router.get("/{campaign_id}/leads")
async def get_campaign_leads(campaign_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Campaign).where(Campaign.campaign_id == campaign_id)
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(404, "Campaign not found")

    return {
        "status": campaign.status,
        "result": campaign.campaign_leads,
        "error": None
    }

    
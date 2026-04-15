from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4

from app.db.database import get_db
from app.models.saved_lead import SavedLead

router = APIRouter()


# POST /api/saved/create
@router.post("/create")
async def create_saved_lead(
    campaign_id: str,
    lead_data: dict,
    db: AsyncSession = Depends(get_db)
):
    lead = SavedLead(
        lead_id=str(uuid4()),
        campaign_id=campaign_id,
        lead_data=lead_data
    )

    db.add(lead)
    await db.commit()

    return {"success": True}


# GET /api/saved
@router.get("/")
async def get_saved_leads(campaign_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SavedLead).where(SavedLead.campaign_id == campaign_id)
    )
    leads = result.scalars().all()

    return leads


# GET /api/saved/{lead_id}
@router.get("/{lead_id}")
async def get_saved_lead(lead_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SavedLead).where(SavedLead.lead_id == lead_id)
    )
    lead = result.scalar_one_or_none()

    if not lead:
        raise HTTPException(404, "Lead not found")

    return lead
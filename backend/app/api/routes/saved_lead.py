from app.models.campaign import Campaign
from app.models.user import User
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4

from app.db.database import get_db
from app.models.saved_lead import SavedLead
from app.auth.user import get_db_user

router = APIRouter()


# POST /api/saved/create
@router.post("/create")
async def create_saved_lead(
    campaign_id: str,
    lead_data: dict,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Campaign).where(
            Campaign.campaign_id == campaign_id,
            Campaign.user_id == user.clerk_id
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(404, "Campaign not found")

    target_id = lead_data.get("id")
    if target_id:
        existing = await db.execute(
            select(SavedLead).where(
                SavedLead.campaign_id == campaign_id,
                SavedLead.lead_data["id"].astext == str(target_id)
            )
        )
        if existing.scalars().first():
            return {"success": True, "already_saved": True}

    lead = SavedLead(
        lead_id=str(uuid4()),
        campaign_id=campaign_id,
        name=lead_data.get("title"),
        lead_data=lead_data
    )

    db.add(lead)
    await db.commit()

    return {"success": True, "lead_id": lead.lead_id}

# GET /api/saved
@router.get("/")
async def get_saved_leads(
    campaign_id: str,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Campaign).where(
            Campaign.campaign_id == campaign_id,
            Campaign.user_id == user.clerk_id
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(404, "Campaign not found")

    result = await db.execute(
        select(SavedLead).where(SavedLead.campaign_id == campaign_id)
    )
    leads = result.scalars().all()

    return [
        {
            "lead_id": l.lead_id,
            "campaign_id": l.campaign_id,
            "name": l.name,
            "lead_data": l.lead_data,
            "created_at": l.created_at.isoformat() if l.created_at else None
        }
        for l in leads
    ]

# DELETE /api/saved/{campaign_id}/{lead_id}
@router.delete("/{campaign_id}/{lead_id}")
async def delete_saved_lead(
    campaign_id: str,
    lead_id: str,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db)
):
    camp_result = await db.execute(
        select(Campaign).where(
            Campaign.campaign_id == campaign_id,
            Campaign.user_id == user.clerk_id
        )
    )
    if not camp_result.scalar_one_or_none():
        raise HTTPException(404, "Campaign not found")

    result = await db.execute(
        select(SavedLead).where(
            SavedLead.campaign_id == campaign_id,
            (SavedLead.lead_id == lead_id) | (SavedLead.lead_data["id"].astext == lead_id)
        )
    )
    saved_lead = result.scalars().first()
    if saved_lead:
        await db.delete(saved_lead)
        await db.commit()
    return {"success": True}

# GET /api/saved/{lead_id}
@router.get("/{lead_id}")
async def get_saved_lead(
    lead_id: str,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(SavedLead, Campaign)
        .join(Campaign, SavedLead.campaign_id == Campaign.campaign_id)
        .where(
            SavedLead.lead_id == lead_id,
            Campaign.user_id == user.clerk_id
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(404, "Lead not found")
    lead, _ = row
    return lead
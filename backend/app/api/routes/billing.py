"""Credits for the signed-in user (spec §5.5). Payments come later (F2.2)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.campaign_runs import quote_for
from app.auth.user import get_db_user
from app.billing import ledger
from app.db.database import get_db
from app.models.campaign import Campaign
from app.models.user import User

router = APIRouter()


@router.get("/balance")
async def balance(user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    data = await ledger.summary(db, user.user_id)
    await db.commit()  # first read creates the Free plan and welcome credits
    return data


@router.get("/history")
async def history(user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    await ledger.ensure_account(db, user.user_id)
    await db.commit()
    return {"entries": await ledger.history(db, user.user_id)}


@router.get("/quote/{campaign_id}")
async def quote(campaign_id: str, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    """What starting (or re-running) this campaign's search costs, and the balance, shown before Run."""
    campaign = (await db.execute(
        select(Campaign).where(Campaign.campaign_id == campaign_id, Campaign.user_id == user.user_id)
    )).scalar_one_or_none()
    if campaign is None:
        raise HTTPException(404, "Campaign not found")
    q = await quote_for(db, campaign, campaign.campaign_details or {})
    data = await ledger.summary(db, user.user_id)
    await db.commit()
    return {"credits": q.credits, "platforms": q.platforms, "find_more": q.find_more,
            "balance": data["balance"], "enough": data["balance"] >= q.credits}

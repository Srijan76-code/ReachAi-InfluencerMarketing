"""Permissions for the founder's agent (F9.8, 8b). All of these need the website sign-in: a personal API key is refused
(default deny, app/auth/api_key_access.py), so an agent can never approve, widen or restore its own permissions."""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import grants
from app.auth.user import get_db_user
from app.db.database import get_db
from app.models.user import User

router = APIRouter()


class DecisionIn(BaseModel):
    code: str = Field(max_length=20)
    approve: bool
    days: Optional[int] = Field(None, ge=1, le=grants.MAX_DAYS)
    per_day: Optional[int] = Field(None, ge=1, le=100)
    mode: Optional[str] = Field(None, pattern="^(ask|unattended)$")


@router.get("/api/grants")
async def list_grants(user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    return {"grants": await grants.listing(db, user.user_id)}


@router.get("/api/grants/lookup")
async def lookup(code: str, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    return await grants.lookup(db, user.user_id, code)


@router.post("/api/grants/decision")
async def decision(body: DecisionIn, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    return await grants.decide(db, user.user_id, body.code, body.approve, days=body.days, per_day=body.per_day, mode=body.mode)


@router.delete("/api/grants/{grant_id}")
async def revoke(grant_id: str, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    return await grants.revoke(db, user.user_id, grant_id)

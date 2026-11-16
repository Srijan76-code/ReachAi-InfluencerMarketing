"""Device login endpoints (F9.8, 8a). `start` and `poll` are called by an agent or CLI with no sign-in; `lookup` and
`decision` are the founder's, from the website, signed in (a personal key is refused there: an agent can't approve itself)."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import device
from app.auth.user import get_db_user
from app.db.database import get_db
from app.mcp.config import app_url
from app.models.user import User

router = APIRouter()


class StartIn(BaseModel):
    client_name: str | None = Field(None, max_length=200, description="What the agent calls itself, e.g. 'Claude Code'.")


class PollIn(BaseModel):
    device_code: str = Field(min_length=10, max_length=200)


class DecisionIn(BaseModel):
    code: str = Field(max_length=20)
    approve: bool


def _ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    return (forwarded.split(",")[0].strip() if forwarded else None) or (request.client.host if request.client else None)


@router.post("/api/device/start")
async def start(body: StartIn, request: Request, db: AsyncSession = Depends(get_db)):
    out = await device.start(db, body.client_name, _ip(request))
    return {**out, "verification_url": f"{app_url()}/device?code={out['user_code']}"}


@router.post("/api/device/poll")
async def poll(body: PollIn, db: AsyncSession = Depends(get_db)):
    return await device.poll(db, body.device_code)


@router.get("/api/device/lookup")
async def lookup(code: str, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    return await device.lookup(db, code)


@router.post("/api/device/decision")
async def decision(body: DecisionIn, user: User = Depends(get_db_user), db: AsyncSession = Depends(get_db)):
    return await device.decide(db, user.user_id, body.code, body.approve)

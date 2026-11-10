"""Personal API keys for agent access over MCP (spec §15.2). Signed-in web users only."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.user import get_db_user
from app.db.database import get_db
from app.mcp.auth import generate_api_key
from app.models.api_key import ApiKey
from app.models.user import User

router = APIRouter()

MAX_ACTIVE_KEYS = 10


class CreateKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=60)


def _row(key: ApiKey) -> dict:
    return {
        "key_id": key.key_id,
        "name": key.name,
        "prefix": key.prefix,
        "created_at": key.created_at.isoformat() if key.created_at else None,
        "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
    }


# POST /api/keys
@router.post("", status_code=201)
async def create_api_key(
    body: CreateKeyRequest,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
):
    active = await db.scalar(
        select(func.count()).select_from(ApiKey).where(ApiKey.user_id == user.user_id, ApiKey.revoked_at.is_(None))
    )
    if (active or 0) >= MAX_ACTIVE_KEYS:
        raise HTTPException(400, f"You can have at most {MAX_ACTIVE_KEYS} active keys. Revoke one first.")

    token, prefix, digest = generate_api_key()
    key = ApiKey(user_id=user.user_id, name=body.name.strip(), prefix=prefix, key_hash=digest)
    db.add(key)
    await db.commit()
    await db.refresh(key)
    # The full key is returned this once and cannot be recovered later.
    return {**_row(key), "key": token}


# GET /api/keys
@router.get("")
async def list_api_keys(
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.user_id == user.user_id, ApiKey.revoked_at.is_(None))
        .order_by(ApiKey.created_at.desc())
    )
    return [_row(k) for k in result.scalars().all()]


# DELETE /api/keys/{key_id}
@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ApiKey).where(ApiKey.key_id == key_id, ApiKey.user_id == user.user_id))
    key = result.scalar_one_or_none()
    if key is None:
        raise HTTPException(404, "Key not found")
    if key.revoked_at is None:
        key.revoked_at = datetime.now(timezone.utc)
        await db.commit()
    return {"success": True}

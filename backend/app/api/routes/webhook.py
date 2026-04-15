from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert
from uuid import uuid4

from app.db.database import AsyncSessionLocal
from app.models.user import User

router = APIRouter()


@router.post("/clerk")
async def clerk_webhook(request: Request):

    payload = await request.json()

    event_type = payload.get("type")
    data = payload.get("data")

    # 👉 only handle user creation
    if event_type == "user.created":

        clerk_id = data["id"]

        async with AsyncSessionLocal() as db:
            user = User(
                user_id=str(uuid4()),
                clerk_id=clerk_id,
                credits=10
            )

            db.add(user)
            await db.commit()

        return {"status": "user created"}

    return {"status": "ignored"}
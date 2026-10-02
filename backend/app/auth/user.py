import logging

from fastapi import Depends, Request, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.database import AsyncSessionLocal
from app.models.user import User

import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

import os
from dotenv import load_dotenv

load_dotenv()

# Clerk JWKS endpoint — must match your Clerk instance domain
CLERK_JWKS_URL = os.getenv(
    "CLERK_JWKS_URL",
    "https://tidy-redfish-49.clerk.accounts.dev/.well-known/jwks.json"
)

jwks_client = PyJWKClient(CLERK_JWKS_URL)


async def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization")
    token = None

    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    elif request.query_params.get("token"):
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization token")

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )

        return decoded

    except jwt.ExpiredSignatureError:
        logger.warning("Clerk JWT has expired")
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid Clerk JWT: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"Unexpected auth error: {e}", exc_info=True)
        raise HTTPException(status_code=401, detail="Authentication failed")


import time

_USER_CACHE: dict[str, tuple[User, float]] = {}
_USER_CACHE_TTL = 120.0


async def get_db_user(user=Depends(get_current_user)):
    clerk_id = user["sub"]
    now = time.time()
    cached = _USER_CACHE.get(clerk_id)
    if cached and (now - cached[1]) < _USER_CACHE_TTL:
        return cached[0]

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.clerk_id == clerk_id)
        )
        db_user = result.scalar()

        if not db_user:
            try:
                db_user = User(
                    clerk_id=clerk_id,
                    credits=10
                )
                db.add(db_user)
                await db.commit()
                await db.refresh(db_user)
                logger.info(f"Created new user for clerk_id={clerk_id}")

            except IntegrityError:
                await db.rollback()

                # fetch again (race condition safe)
                result = await db.execute(
                    select(User).where(User.clerk_id == clerk_id)
                )
                db_user = result.scalar()

        if db_user:
            db.expunge(db_user)
            _USER_CACHE[clerk_id] = (db_user, now)

        return db_user
"""Billing tests run on SQLite, and also on real Postgres when PG_TEST_URL is set (a throwaway database:
its billing tables are dropped). The concurrency test needs Postgres (advisory locks)."""

import os

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
import app.models  # noqa: F401  (register every table)
from app.models.campaign import Campaign, CampaignStatus
from app.models.user import User


@compiles(JSONB, "sqlite")
def _jsonb_as_json(type_, compiler, **kw):
    return "JSON"


TABLES = ["users", "campaigns", "credit_ledger", "credit_reservations", "subscriptions", "payments", "billing_events", "referral_codes", "referrals"]
BACKENDS = ["sqlite"] + (["postgres"] if os.getenv("PG_TEST_URL") else [])
BRIEF = {"brand": {"name": "DataLaunch"}, "campaign": {"goal": "signups"}}


@pytest_asyncio.fixture(params=BACKENDS)
async def db(request):
    if request.param == "sqlite":
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    else:
        engine = create_async_engine(os.environ["PG_TEST_URL"])
    tables = [Base.metadata.tables[t] for t in TABLES]
    drop = "DROP TABLE IF EXISTS " + ", ".join(reversed(TABLES)) + " CASCADE"
    async with engine.begin() as conn:
        if request.param == "postgres":
            await conn.execute(text(drop))
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))
    factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    factory.backend = request.param
    async with factory() as s:
        s.add_all([User(user_id="u1", clerk_id="clerk_1"), User(user_id="u2", clerk_id="clerk_2")])
        await s.flush()
        for cid in ("c1", "c2", "c3"):
            s.add(Campaign(campaign_id=cid, user_id="u1", name=cid, status=CampaignStatus.CREATED, campaign_details=BRIEF))
        await s.commit()
    yield factory
    async with engine.begin() as conn:
        if request.param == "postgres":
            await conn.execute(text(drop))
        else:
            await conn.run_sync(lambda c: Base.metadata.drop_all(c, tables=tables))
    await engine.dispose()

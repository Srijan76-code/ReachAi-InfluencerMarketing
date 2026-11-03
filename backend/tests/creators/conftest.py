"""Run every creator-database test on SQLite, and also on real Postgres + pgvector when
PG_TEST_URL is set (a throwaway database, e.g. postgresql+asyncpg://postgres@localhost:5433/reachai_unit).
The Postgres database is wiped between tests, so never point this at real data."""

import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
import app.models.creator  # noqa: F401  (register tables)

TABLES = ["creator_persons", "creators", "creator_snapshots", "creator_judgments", "person_links", "creator_embeddings"]
BACKENDS = ["sqlite"] + (["postgres"] if os.getenv("PG_TEST_URL") else [])


@pytest_asyncio.fixture(params=BACKENDS)
async def db(request):
    if request.param == "sqlite":
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    else:
        engine = create_async_engine(os.environ["PG_TEST_URL"])
    tables = [Base.metadata.tables[t] for t in TABLES]
    async with engine.begin() as conn:
        if request.param == "postgres":
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text("DROP TABLE IF EXISTS " + ", ".join(TABLES) + " CASCADE"))
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))
    factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    factory.backend = request.param
    yield factory
    async with engine.begin() as conn:
        if request.param == "postgres":
            await conn.execute(text("DROP TABLE IF EXISTS " + ", ".join(TABLES) + " CASCADE"))
        else:
            await conn.run_sync(lambda c: Base.metadata.drop_all(c, tables=tables))
    await engine.dispose()

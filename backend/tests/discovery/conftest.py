import os

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.db.base import Base
import app.models  # noqa: F401  (register all tables)
from tests.foundations.conftest import cost_log  # noqa: F401  (shared fixture)

TABLES = ["cache_entries", "cost_events", "creator_persons", "creators", "creator_snapshots", "creator_judgments",
          "person_links", "creator_embeddings", "run_strategy", "run_candidates"]


def make_engine(tmp_path):
    """Like production: a separate connection per session (parallel graph steps write at the same
    time). Real Postgres + pgvector when PG_TEST_URL is set, else a SQLite file that waits on locks."""
    if os.getenv("PG_TEST_URL"):
        return create_async_engine(os.environ["PG_TEST_URL"], poolclass=NullPool), True
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    return create_async_engine(url, poolclass=NullPool, connect_args={"timeout": 30}), False


async def create_tables(engine, is_pg, names):
    tables = [Base.metadata.tables[t] for t in names]
    async with engine.begin() as conn:
        if is_pg:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            # always clear the campaign tables too: other tests in the same database may have created them
            await conn.execute(text("DROP TABLE IF EXISTS " + ", ".join(list(reversed(names)) + ["campaigns", "users"]) + " CASCADE"))
            await conn.execute(text("DROP TYPE IF EXISTS campaignstatus CASCADE"))
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))


@pytest_asyncio.fixture
async def sf(tmp_path):
    """Every table the discovery graph touches."""
    engine, is_pg = make_engine(tmp_path)
    await create_tables(engine, is_pg, TABLES)
    yield sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()

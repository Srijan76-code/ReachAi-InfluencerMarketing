import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.billing import costs
from app.db.base import Base
from app.models.cache_entry import CacheEntry  # noqa: F401  (register table)
from app.models.cost_event import CostEvent  # noqa: F401


@pytest.fixture
def cost_log():
    """Capture cost records in memory instead of writing to Postgres."""
    records = []

    async def sink(record):
        records.append(record)

    previous = costs.set_sink(sink)
    yield records
    costs.set_sink(previous)


@pytest_asyncio.fixture
async def session_factory():
    """In-memory SQLite with only the foundation tables."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [Base.metadata.tables["cache_entries"], Base.metadata.tables["cost_events"]]
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=tables))
    yield sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
import app.models  # noqa: F401  (register all tables)
from tests.foundations.conftest import cost_log  # noqa: F401  (shared fixture)

TABLES = ["cache_entries", "cost_events", "creator_persons", "creators", "creator_snapshots", "creator_judgments",
          "person_links", "creator_embeddings", "run_strategy", "run_candidates"]


@pytest_asyncio.fixture
async def sf():
    """In-memory SQLite with every table the discovery graph touches."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=[Base.metadata.tables[t] for t in TABLES]))
    yield sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()

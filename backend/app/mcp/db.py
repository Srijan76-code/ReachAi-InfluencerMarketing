"""Database sessions for MCP tools. Imported lazily so tests can swap the session factory."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

_factory = None


def set_session_factory(factory) -> None:
    """Tests call this with an in-memory database factory. Pass None to go back to the app's."""
    global _factory
    _factory = factory


def _default_factory():
    from app.db.database import AsyncSessionLocal

    return AsyncSessionLocal


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    factory = _factory or _default_factory()
    async with factory() as session:
        yield session

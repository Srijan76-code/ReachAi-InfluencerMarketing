"""Shared read-through cache in Postgres (spec §4.14).

    value, hit = await cached("search", {"platform": "youtube", "q": q}, timedelta(hours=48), fetch)

- Works across serverless calls (LangGraph's InMemoryCache does not).
- Values must be JSON-serialisable.
- A failed cache read or write never fails the caller; it just computes the value.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Optional

from sqlalchemy import delete, select

from app.models.cache_entry import CacheEntry

logger = logging.getLogger(__name__)

# Default TTLs per namespace (spec §4.14 table).
TTL = {
    "search": timedelta(hours=48),
    "llm": timedelta(days=7),
}


def cache_key(parts: Any) -> str:
    """Stable sha256 over JSON with sorted keys."""
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _default_session_factory():
    from app.db.database import AsyncSessionLocal

    return AsyncSessionLocal


_MISS = object()


async def get_cached(namespace: str, key: str, *, session_factory=None) -> Any:
    """Return the stored value, or _MISS. Values are wrapped so None/[]/0 are valid cached results."""
    factory = session_factory or _default_session_factory()
    async with factory() as session:
        row = (
            await session.execute(select(CacheEntry).where(CacheEntry.namespace == namespace, CacheEntry.key == key))
        ).scalar_one_or_none()
        if row is None or _aware(row.expires_at) <= _now():
            return _MISS
        return row.value.get("v") if isinstance(row.value, dict) else row.value


async def set_cached(namespace: str, key: str, value: Any, ttl: timedelta, *, session_factory=None) -> None:
    factory = session_factory or _default_session_factory()
    async with factory() as session:
        await session.merge(CacheEntry(namespace=namespace, key=key, value={"v": value}, expires_at=_now() + ttl))
        await session.commit()


async def cached(
    namespace: str,
    key_parts: Any,
    ttl: Optional[timedelta],
    compute: Callable[[], Awaitable[Any]],
    *,
    session_factory=None,
) -> tuple[Any, bool]:
    """Return (value, was_cache_hit). Computes and stores the value on a miss or expiry."""
    key = cache_key(key_parts)
    ttl = ttl or TTL.get(namespace, timedelta(hours=24))
    try:
        hit = await get_cached(namespace, key, session_factory=session_factory)
        if hit is not _MISS:
            return hit, True
    except Exception:
        logger.exception("Cache read failed for %s", namespace)

    value = await compute()
    try:
        await set_cached(namespace, key, value, ttl, session_factory=session_factory)
    except Exception:
        logger.exception("Cache write failed for %s", namespace)
    return value, False


async def purge_expired(*, session_factory=None) -> int:
    """Delete expired rows. Run from a nightly Inngest cron."""
    factory = session_factory or _default_session_factory()
    async with factory() as session:
        result = await session.execute(delete(CacheEntry).where(CacheEntry.expires_at <= _now()))
        await session.commit()
        return result.rowcount or 0

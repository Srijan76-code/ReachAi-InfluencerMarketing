"""LangGraph node cache stored in Postgres (`cache_entries`), replacing InMemoryCache.

InMemoryCache disappears between serverless requests, so it never helped retries or later
runs. This keeps node results across requests. Async only: the discovery graph runs async.
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from typing import Mapping, Optional, Sequence

from langgraph.cache.base import BaseCache, FullKey, Namespace
from sqlalchemy import delete, select

from app.models.cache_entry import CacheEntry

PREFIX = "lg:"
DEFAULT_TTL = timedelta(days=7)  # used when a node's CachePolicy has no ttl


def _ns(namespace: Namespace) -> str:
    return PREFIX + "/".join(namespace)


def _factory(session_factory):
    if session_factory is not None:
        return session_factory
    from app.db.database import AsyncSessionLocal

    return AsyncSessionLocal


class PostgresNodeCache(BaseCache):
    def __init__(self, *, session_factory=None, serde=None):
        super().__init__(serde=serde)
        self._session_factory = session_factory

    async def aget(self, keys: Sequence[FullKey]) -> dict:
        if not keys:
            return {}
        now = datetime.now(timezone.utc)
        out: dict = {}
        async with _factory(self._session_factory)() as session:
            for namespace, key in keys:
                row = await session.get(CacheEntry, (_ns(namespace), key))
                if row is None:
                    continue
                expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
                if expires <= now:
                    continue
                value = row.value or {}
                try:
                    out[(namespace, key)] = self.serde.loads_typed((value["enc"], base64.b64decode(value["b64"])))
                except (KeyError, ValueError, TypeError):
                    continue  # unreadable entry: treat as a miss
        return out

    async def aset(self, pairs: Mapping[FullKey, tuple[object, Optional[int]]]) -> None:
        if not pairs:
            return
        now = datetime.now(timezone.utc)
        async with _factory(self._session_factory)() as session:
            for (namespace, key), (value, ttl) in pairs.items():
                enc, raw = self.serde.dumps_typed(value)
                expires = now + (timedelta(seconds=ttl) if ttl is not None else DEFAULT_TTL)
                await session.merge(
                    CacheEntry(
                        namespace=_ns(namespace),
                        key=key,
                        value={"enc": enc, "b64": base64.b64encode(raw).decode()},
                        expires_at=expires,
                    )
                )
            await session.commit()

    async def aclear(self, namespaces: Optional[Sequence[Namespace]] = None) -> None:
        async with _factory(self._session_factory)() as session:
            if namespaces is None:
                await session.execute(delete(CacheEntry).where(CacheEntry.namespace.like(PREFIX + "%")))
            else:
                await session.execute(delete(CacheEntry).where(CacheEntry.namespace.in_([_ns(n) for n in namespaces])))
            await session.commit()

    def get(self, keys):  # pragma: no cover - the graph runs async
        raise NotImplementedError("PostgresNodeCache is async only")

    def set(self, pairs):  # pragma: no cover
        raise NotImplementedError("PostgresNodeCache is async only")

    def clear(self, namespaces=None):  # pragma: no cover
        raise NotImplementedError("PostgresNodeCache is async only")

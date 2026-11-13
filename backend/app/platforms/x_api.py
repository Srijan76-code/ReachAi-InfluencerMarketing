"""Thin async client for X data through twitterapi.io (spec §6.1).

Only the calls the adapter needs. Every call logs its cost in cost_events (CLAUDE.md rule 6):
twitterapi.io bills 15 credits per tweet returned, 18 per profile, with a 15-credit minimum per call,
and 100,000 credits = $1. The key comes from X_PROVIDER_API_KEY and is never logged.
"""

from __future__ import annotations

import asyncio
import os
import time
from decimal import Decimal
from typing import Any, Optional, Protocol

import httpx

from app.billing.costs import CostContext, CostRecord, record_cost
from app.core import config

BASE_URL = "https://api.twitterapi.io"
CREDITS_PER_USD = 100_000
CREDITS_PER_TWEET = 15
CREDITS_PER_PROFILE = 18
MIN_CREDITS_PER_CALL = 15
RETRIES_ON_429 = 3


class XAPIError(RuntimeError):
    def __init__(self, status: int, reason: str):
        super().__init__(f"X provider error {status}: {reason}")
        self.status = status
        self.reason = reason

    @property
    def out_of_credits(self) -> bool:
        return self.status == 402


class XAPI(Protocol):
    """What the adapter needs. Tests replace it with a recorded-response fake."""

    async def advanced_search(self, query: str, query_type: str = "Top", cursor: Optional[str] = None) -> dict: ...

    async def last_tweets(self, user_id: str, cursor: Optional[str] = None) -> dict: ...

    async def user_info(self, user_name: str) -> dict: ...


class _Pacer:
    """Spaces requests to stay under the provider's per-second limit (shared by all calls of one client)."""

    def __init__(self, per_second: float):
        self._gap = 1.0 / max(per_second, 0.01)
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            delay = self._next - now
            self._next = max(now, self._next) + self._gap
        if delay > 0:
            await asyncio.sleep(delay)


def cost_usd(credits: int) -> Decimal:
    return Decimal(credits) / Decimal(CREDITS_PER_USD)


class HttpXAPI:
    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        context: Optional[CostContext] = None,
        client: Optional[httpx.AsyncClient] = None,
        timeout: float = 30.0,
        per_second: Optional[float] = None,
    ):
        self._key = api_key or os.getenv("X_PROVIDER_API_KEY")
        if not self._key:
            raise XAPIError(0, "X_PROVIDER_API_KEY is not set")
        self._context = context or CostContext()
        self._client = client or httpx.AsyncClient(base_url=BASE_URL, timeout=timeout)
        self._pacer = _Pacer(per_second or config.X_REQUESTS_PER_SECOND)
        self.credits_used = 0

    async def _get(self, path: str, params: dict, sku: str, per_item: int, items_key: str) -> dict:
        clean = {k: v for k, v in params.items() if v is not None}
        for attempt in range(RETRIES_ON_429 + 1):
            await self._pacer.wait()
            response = await self._client.get(path, params=clean, headers={"x-api-key": self._key})
            if response.status_code != 429 or attempt == RETRIES_ON_429:
                break
            await asyncio.sleep(1.5 * (attempt + 1))
        if response.status_code != 200:
            raise XAPIError(response.status_code, response.text[:200])
        data = response.json()
        if isinstance(data, dict) and data.get("status") == "error":
            raise XAPIError(200, str(data.get("msg") or data.get("message") or "error")[:200])
        items = _items(data, items_key)
        credits = max(MIN_CREDITS_PER_CALL, per_item * len(items))
        self.credits_used += credits
        await record_cost(CostRecord(provider="twitterapi", sku=sku, route="x_api", context=self._context,
                                     units=len(items), usd=cost_usd(credits)))
        return data

    async def advanced_search(self, query: str, query_type: str = "Top", cursor: Optional[str] = None) -> dict:
        return await self._get("/twitter/tweet/advanced_search", {"query": query, "queryType": query_type, "cursor": cursor},
                               "advanced_search", CREDITS_PER_TWEET, "tweets")

    async def last_tweets(self, user_id: str, cursor: Optional[str] = None) -> dict:
        return await self._get("/twitter/user/last_tweets", {"userId": user_id, "cursor": cursor, "includeReplies": "false"},
                               "last_tweets", CREDITS_PER_TWEET, "tweets")

    async def user_info(self, user_name: str) -> dict:
        return await self._get("/twitter/user/info", {"userName": user_name}, "user_info", CREDITS_PER_PROFILE, "data")

    async def aclose(self) -> None:
        await self._client.aclose()


def _items(data: Any, key: str) -> list:
    """Tweets or profiles in a response (some endpoints nest them under "data")."""
    if not isinstance(data, dict):
        return []
    if key == "data":
        return [data["data"]] if isinstance(data.get("data"), dict) else []
    found = data.get(key)
    if found is None and isinstance(data.get("data"), dict):
        found = data["data"].get(key)
    return found if isinstance(found, list) else []

"""Thin async client for the YouTube Data API v3 (spec §4.8).

Only the five calls the adapter needs. Every call records its quota cost in cost_events
(YouTube is free in money but limited to 10,000 units a day per project).
The API key comes from YOUTUBE_API_KEY and is never logged.
"""

from __future__ import annotations

import os
from typing import Any, Optional, Protocol

import httpx

from app.billing.costs import CostContext, CostRecord, record_cost

BASE_URL = "https://www.googleapis.com/youtube/v3"

# Quota units per call (YouTube Data API v3 quota table).
QUOTA = {"search": 100, "channels": 1, "playlistItems": 1, "videos": 1, "commentThreads": 1}


class YouTubeAPIError(RuntimeError):
    def __init__(self, status: int, reason: str):
        super().__init__(f"YouTube API error {status}: {reason}")
        self.status = status
        self.reason = reason

    @property
    def quota_exceeded(self) -> bool:
        """Out of quota for now: stop calling YouTube for the rest of the run. Includes
        rateLimitExceeded, which YouTube also returns once the daily search allowance is used up."""
        reason = self.reason.lower()
        return self.status == 403 and ("quota" in reason or reason in STOP_REASONS)


STOP_REASONS = {"ratelimitexceeded", "userratelimitexceeded", "dailylimitexceeded"}


class YouTubeAPI(Protocol):
    """What the adapter needs. Tests replace it with a recorded-response fake."""

    async def search(self, **params: Any) -> dict: ...
    async def channels(self, **params: Any) -> dict: ...
    async def playlist_items(self, **params: Any) -> dict: ...
    async def videos(self, **params: Any) -> dict: ...


class HttpYouTubeAPI:
    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        context: Optional[CostContext] = None,
        client: Optional[httpx.AsyncClient] = None,
        timeout: float = 20.0,
    ):
        self._key = api_key or os.getenv("YOUTUBE_API_KEY")
        if not self._key:
            raise YouTubeAPIError(0, "YOUTUBE_API_KEY is not set")
        self._context = context or CostContext()
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self.units_used = 0

    async def _get(self, resource: str, params: dict) -> dict:
        clean = {k: v for k, v in params.items() if v is not None}
        response = await self._client.get(f"{BASE_URL}/{resource}", params={**clean, "key": self._key})
        units = QUOTA.get(resource, 1)
        self.units_used += units
        await record_cost(
            CostRecord(provider="youtube", sku=resource, route="youtube_api", context=self._context, units=units, usd=0)
        )
        if response.status_code != 200:
            try:
                err = response.json().get("error", {})
                reason = ",".join(e.get("reason", "") for e in err.get("errors", [])) or err.get("message", "")
            except ValueError:
                reason = response.text[:200]
            raise YouTubeAPIError(response.status_code, reason)
        return response.json()

    async def search(self, **params: Any) -> dict:
        return await self._get("search", params)

    async def channels(self, **params: Any) -> dict:
        return await self._get("channels", params)

    async def playlist_items(self, **params: Any) -> dict:
        return await self._get("playlistItems", params)

    async def videos(self, **params: Any) -> dict:
        return await self._get("videos", params)

    async def comment_threads(self, **params: Any) -> dict:
        return await self._get("commentThreads", params)

    async def aclose(self) -> None:
        await self._client.aclose()

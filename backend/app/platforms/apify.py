"""Thin async client for Apify actors (spec §6.2, §6.3).

- Runs are started, then polled (`waitForFinish`), then their dataset is read. Long synchronous calls
  get cut off by proxies, and polling lets a retried search pick up the same run instead of paying again:
  the run id is remembered under a key made from the actor and its input.
- Every run passes `maxTotalChargeUsd`, so a run can never cost more than we planned.
- Every run logs a cost_events row from the events Apify actually charged (CLAUDE.md rule 6).
- The token comes from APIFY_TOKEN and is never logged.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any, Awaitable, Callable, Optional, Protocol

import httpx

from app.billing.costs import CostContext, CostRecord, record_cost

BASE_URL = "https://api.apify.com/v2"
POLL_SECONDS = 30  # Apify holds each status request open up to this long
RUN_DEADLINE_SECONDS = 240  # give up waiting after this; a retry picks the run up again
RUN_MEMO_TTL = timedelta(hours=2)

# Free-tier prices per charged event (USD), checked on Nov 13 2026. Paid Apify plans pay less.
PRICES: dict[str, dict[str, float]] = {
    "apify/instagram-search-scraper": {"result": 0.0027},
    "apify/instagram-hashtag-scraper": {"result": 0.0026},
    "apify/instagram-profile-scraper": {"profile": 0.0026},
    "apify/instagram-reel-scraper": {"reel": 0.0026, "actor-start": 0.001},
}

TERMINAL = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}


class ApifyError(RuntimeError):
    def __init__(self, status: int, reason: str):
        super().__init__(f"Apify error {status}: {reason}")
        self.status = status
        self.reason = reason

    @property
    def out_of_credits(self) -> bool:
        return self.status == 402 or ("usage" in self.reason.lower() and "limit" in self.reason.lower())


class ApifyAPI(Protocol):
    """What adapters need. Tests replace it with a recorded-response fake."""

    async def run(self, actor: str, run_input: dict, *, max_usd: float) -> list[dict]: ...


@dataclass
class RunMemo:
    """Where run ids are remembered between retries (Postgres cache in production)."""

    get: Callable[[str], Awaitable[Optional[str]]]
    set: Callable[[str, str], Awaitable[None]]


def memory_memo() -> RunMemo:
    store: dict[str, str] = {}

    async def get(key: str) -> Optional[str]:
        return store.get(key)

    async def set_(key: str, value: str) -> None:
        store[key] = value

    return RunMemo(get, set_)


def db_memo(session_factory_getter: Callable[[], Any] = lambda: None) -> RunMemo:
    from app.discovery.cache import cache_key, get_cached, set_cached

    async def get(key: str) -> Optional[str]:
        return await get_cached("apify_run", cache_key(key), session_factory=session_factory_getter())

    async def set_(key: str, value: str) -> None:
        await set_cached("apify_run", cache_key(key), value, RUN_MEMO_TTL, session_factory=session_factory_getter())

    return RunMemo(get, set_)


def charged_usd(actor: str, events: dict[str, int]) -> Decimal:
    prices = PRICES.get(actor, {})
    return sum((Decimal(str(prices.get(name, 0))) * int(count or 0) for name, count in (events or {}).items()), Decimal(0))


class HttpApify:
    def __init__(
        self,
        token: Optional[str] = None,
        *,
        context: Optional[CostContext] = None,
        memo: Optional[RunMemo] = None,
        client: Optional[httpx.AsyncClient] = None,
        timeout: float = POLL_SECONDS + 15,
        deadline_seconds: float = RUN_DEADLINE_SECONDS,
    ):
        self._token = token or os.getenv("APIFY_TOKEN") or os.getenv("APIFY_API_TOKEN")
        if not self._token:
            raise ApifyError(0, "APIFY_TOKEN is not set")
        self._context = context or CostContext()
        self._memo = memo or memory_memo()
        self._client = client or httpx.AsyncClient(base_url=BASE_URL, timeout=timeout)
        self._deadline = deadline_seconds

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    async def _call(self, method: str, path: str, **kw) -> Any:
        response = await self._client.request(method, path, headers=self._headers(), **kw)
        if response.status_code >= 400:
            raise ApifyError(response.status_code, response.text[:200])
        return response.json()

    async def run(self, actor: str, run_input: dict, *, max_usd: float) -> list[dict]:
        actor_path = actor.replace("/", "~")
        memo_key = f"{actor}|{sorted(run_input.items())!r}|{self._context.run_id or ''}"
        run_id = await self._memo.get(memo_key)
        if not run_id:
            started = await self._call("POST", f"/acts/{actor_path}/runs", params={"maxTotalChargeUsd": f"{max_usd:.4f}"},
                                       json=run_input)
            run_id = started["data"]["id"]
            await self._memo.set(memo_key, run_id)

        began = time.monotonic()
        while True:
            data = (await self._call("GET", f"/actor-runs/{run_id}", params={"waitForFinish": POLL_SECONDS}))["data"]
            if data.get("status") in TERMINAL:
                break
            if time.monotonic() - began > self._deadline:
                raise ApifyError(408, f"{actor} still running after {int(self._deadline)} s")
            await asyncio.sleep(0)

        usd = charged_usd(actor, data.get("chargedEventCounts") or {})
        status = data["status"]
        items: list[dict] = []
        if status == "SUCCEEDED" or data.get("defaultDatasetId"):
            # an aborted or timed-out run may still have written (and charged for) some items
            got = await self._client.get(f"/datasets/{data['defaultDatasetId']}/items", headers=self._headers(),
                                         params={"clean": "true", "format": "json"})
            if got.status_code < 400:
                items = [i for i in got.json() if isinstance(i, dict) and not i.get("error")]
        await record_cost(CostRecord(provider="apify", sku=actor, route="apify", context=self._context,
                                     units=len(items), usd=usd, meta={"run_id": run_id, "status": status}))
        if status != "SUCCEEDED" and not items:
            raise ApifyError(500, f"{actor} run {status.lower()}: {(data.get('statusMessage') or '')[:120]}")
        return items

    async def aclose(self) -> None:
        await self._client.aclose()

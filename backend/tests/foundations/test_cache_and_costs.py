from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.billing import costs
from app.discovery import cache
from app.models.cost_event import CostEvent


@pytest.mark.asyncio
async def test_cached_computes_once_then_hits(session_factory):
    calls = []

    async def compute():
        calls.append(1)
        return {"ids": ["UC1", "UC2"]}

    parts = {"platform": "youtube", "q": "ai tools", "region": "IN"}
    v1, hit1 = await cache.cached("search", parts, timedelta(hours=1), compute, session_factory=session_factory)
    v2, hit2 = await cache.cached("search", parts, timedelta(hours=1), compute, session_factory=session_factory)
    assert (hit1, hit2) == (False, True)
    assert v1 == v2 == {"ids": ["UC1", "UC2"]}
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_expired_entry_is_recomputed_and_purged(session_factory):
    async def compute():
        return [1]

    parts = {"q": "x"}
    await cache.cached("search", parts, timedelta(seconds=-1), compute, session_factory=session_factory)
    _, hit = await cache.cached("search", parts, timedelta(seconds=-1), compute, session_factory=session_factory)
    assert hit is False
    assert await cache.purge_expired(session_factory=session_factory) == 1


@pytest.mark.asyncio
async def test_cache_failure_still_returns_value():
    def broken_factory():
        raise RuntimeError("db down")

    async def compute():
        return "fresh"

    value, hit = await cache.cached("llm", {"a": 1}, None, compute, session_factory=broken_factory)
    assert (value, hit) == ("fresh", False)


def test_cache_key_is_order_independent():
    assert cache.cache_key({"a": 1, "b": [1, 2]}) == cache.cache_key({"b": [1, 2], "a": 1})


def test_token_cost():
    assert costs.token_cost(1_000_000, 0, 0.042, 0.0) == Decimal("0.042000")
    assert costs.token_cost(10, 10, None, 1.0) is None


@pytest.mark.asyncio
async def test_record_cost_never_raises():
    async def broken(record):
        raise RuntimeError("db down")

    previous = costs.set_sink(broken)
    try:
        await costs.record_cost(costs.CostRecord(provider="groq", sku="m", context=costs.CostContext()))
    finally:
        costs.set_sink(previous)


@pytest.mark.asyncio
async def test_cost_event_row_shape(session_factory):
    async with session_factory() as s:
        s.add(CostEvent(provider="typesafe", sku="jev-1.13.0", route="judge", input_tokens=10, usd=Decimal("0.000001"), run_id="r1"))
        await s.commit()
        row = (await s.execute(select(CostEvent))).scalar_one()
    assert row.event_id and row.run_id == "r1" and row.provider == "typesafe"


@pytest.mark.asyncio
@pytest.mark.parametrize("empty_value", [None, [], 0, "", {}])
async def test_empty_results_are_cached_too(session_factory, empty_value):
    calls = []

    async def compute():
        calls.append(1)
        return empty_value

    for _ in range(2):
        value, _ = await cache.cached("search", {"q": repr(empty_value)}, timedelta(hours=1), compute, session_factory=session_factory)
        assert value == empty_value
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_namespaces_do_not_collide(session_factory):
    async def a():
        return "search-value"

    async def b():
        return "llm-value"

    parts = {"same": "key"}
    va, _ = await cache.cached("search", parts, timedelta(hours=1), a, session_factory=session_factory)
    vb, _ = await cache.cached("llm", parts, timedelta(hours=1), b, session_factory=session_factory)
    assert (va, vb) == ("search-value", "llm-value")


@pytest.mark.asyncio
async def test_compute_error_propagates_and_is_not_cached(session_factory):
    async def failing():
        raise RuntimeError("provider down")

    with pytest.raises(RuntimeError):
        await cache.cached("search", {"q": "x"}, timedelta(hours=1), failing, session_factory=session_factory)

    async def ok():
        return "ok"

    value, hit = await cache.cached("search", {"q": "x"}, timedelta(hours=1), ok, session_factory=session_factory)
    assert (value, hit) == ("ok", False)


@pytest.mark.asyncio
async def test_overwrite_after_expiry_keeps_one_row(session_factory):
    async def v1():
        return 1

    async def v2():
        return 2

    await cache.cached("search", {"q": "y"}, timedelta(seconds=-1), v1, session_factory=session_factory)
    value, _ = await cache.cached("search", {"q": "y"}, timedelta(hours=1), v2, session_factory=session_factory)
    assert value == 2
    async with session_factory() as s:
        from app.models.cache_entry import CacheEntry
        rows = (await s.execute(select(CacheEntry))).scalars().all()
    assert len(rows) == 1


def test_token_cost_handles_missing_tokens():
    assert costs.token_cost(None, None, 1.0, 1.0) == Decimal("0.000000")

import operator
from typing import Annotated, TypedDict

import pytest
from langgraph.graph import END, START, StateGraph
from langgraph.types import CachePolicy

from app.creators.constants import EMBEDDING_DIM
from app.discovery.node_cache import PostgresNodeCache
from app.llm.embeddings import EmbeddingUnavailableError, embed_texts


def fake_provider(calls):
    async def provider(texts, task, context):
        calls.append(list(texts))
        return [[float(len(t))] + [0.0] * (EMBEDDING_DIM - 1) for t in texts]
    return provider


@pytest.mark.asyncio
async def test_embeddings_keep_order_dedupe_and_cache(sf):
    calls = []
    out = await embed_texts(["a", "bb", "a"], session_factory=sf, provider=fake_provider(calls))
    assert [v[0] for v in out] == [1.0, 2.0, 1.0] and calls == [["a", "bb"]]
    again = await embed_texts(["bb", "ccc"], session_factory=sf, provider=fake_provider(calls))
    assert [v[0] for v in again] == [2.0, 3.0] and calls[-1] == ["ccc"]  # "bb" came from the cache
    query = await embed_texts(["a"], task="query", session_factory=sf, provider=fake_provider(calls))
    assert calls[-1] == ["a"] and query[0][0] == 1.0  # query and document embeddings are cached separately


@pytest.mark.asyncio
async def test_embeddings_reject_bad_provider_output(sf):
    async def wrong_dims(texts, task, context):
        return [[0.1, 0.2] for _ in texts]

    async def too_few(texts, task, context):
        return []

    with pytest.raises(EmbeddingUnavailableError):
        await embed_texts(["x"], session_factory=sf, provider=wrong_dims, use_cache=False)
    with pytest.raises(EmbeddingUnavailableError):
        await embed_texts(["x"], session_factory=sf, provider=too_few, use_cache=False)
    assert await embed_texts([], provider=wrong_dims) == []


def test_embeddings_need_a_key(monkeypatch):
    import asyncio

    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(EmbeddingUnavailableError):
        asyncio.run(embed_texts(["x"], use_cache=False))


class S(TypedDict):
    x: int
    log: Annotated[list, operator.add]


@pytest.mark.asyncio
async def test_node_cache_survives_a_new_cache_object(sf):
    """A new PostgresNodeCache (like a new serverless request) still serves the cached node."""
    calls = {"n": 0}

    async def slow_square(s):
        calls["n"] += 1
        return {"log": [s["x"] ** 2]}

    g = StateGraph(S)
    g.add_node("sq", slow_square, cache_policy=CachePolicy(ttl=60))
    g.add_edge(START, "sq")
    g.add_edge("sq", END)

    first = await g.compile(cache=PostgresNodeCache(session_factory=sf)).ainvoke({"x": 4, "log": []})
    second = await g.compile(cache=PostgresNodeCache(session_factory=sf)).ainvoke({"x": 4, "log": []})
    other = await g.compile(cache=PostgresNodeCache(session_factory=sf)).ainvoke({"x": 5, "log": []})
    assert first["log"] == second["log"] == [16] and other["log"] == [25]
    assert calls["n"] == 2  # x=4 ran once, x=5 once

    cache = PostgresNodeCache(session_factory=sf)
    await cache.aclear()
    await g.compile(cache=cache).ainvoke({"x": 4, "log": []})
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_node_cache_expired_and_corrupt_entries_are_misses(sf):
    from app.models.cache_entry import CacheEntry

    cache = PostgresNodeCache(session_factory=sf)
    await cache.aset({(("ns",), "k"): ({"v": 1}, -1)})  # already expired
    assert await cache.aget([(("ns",), "k")]) == {}
    async with sf() as s:
        await s.merge(CacheEntry(namespace="lg:ns", key="bad", value={"oops": True},
                                 expires_at=__import__("datetime").datetime(2099, 1, 1)))
        await s.commit()
    assert await cache.aget([(("ns",), "bad")]) == {}
    await cache.aset({(("ns",), "ok"): ({"v": 2}, None)})
    assert await cache.aget([(("ns",), "ok")]) == {(("ns",), "ok"): {"v": 2}}
    assert await cache.aget([]) == {}

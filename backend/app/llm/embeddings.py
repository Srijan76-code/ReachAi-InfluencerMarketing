"""Text embeddings for similar-creator search and the shortlist (spec §4.4, §4.11).

    vectors = await embed_texts(["..."], task="document", context=ctx)

- Gemini `gemini-embedding-001` at EMBEDDING_DIM (768) dimensions, batched (100 per call).
- Identical texts are embedded once per call and cached in Postgres across runs.
- Each provider call logs a cost_events row (token count estimated from characters).
"""

from __future__ import annotations

import hashlib
import os
from datetime import timedelta
from typing import Literal, Optional, Sequence

from app.billing.costs import CostContext, CostRecord, record_cost
from app.creators.constants import EMBEDDING_DIM, EMBEDDING_MODEL

BATCH = 100
CACHE_TTL = timedelta(days=30)
TASK_TYPES = {"document": "RETRIEVAL_DOCUMENT", "query": "RETRIEVAL_QUERY", "similarity": "SEMANTIC_SIMILARITY"}

Task = Literal["document", "query", "similarity"]


class EmbeddingUnavailableError(RuntimeError):
    pass


def _client():
    key = os.getenv("GOOGLE_API_KEY")
    if not key:
        raise EmbeddingUnavailableError("GOOGLE_API_KEY is not set")
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    return GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL, google_api_key=key)


async def _provider_embed(texts: list[str], task: Task, context: CostContext) -> list[list[float]]:
    client = _client()
    out: list[list[float]] = []
    for i in range(0, len(texts), BATCH):
        batch = texts[i : i + BATCH]
        vectors = await client.aembed_documents(
            batch, task_type=TASK_TYPES[task], output_dimensionality=EMBEDDING_DIM
        )
        out.extend([list(map(float, v)) for v in vectors])
        await record_cost(
            CostRecord(
                provider="google",
                sku=EMBEDDING_MODEL,
                route=f"embed:{task}",
                context=context,
                input_tokens=sum(len(t) for t in batch) // 4,  # estimate; the API doesn't return counts here
                units=len(batch),
            )
        )
    return out


def text_key(text: str, task: Task) -> str:
    return hashlib.sha256(f"{EMBEDDING_MODEL}|{EMBEDDING_DIM}|{task}|{text}".encode()).hexdigest()


async def embed_texts(
    texts: Sequence[str],
    *,
    task: Task = "document",
    context: Optional[CostContext] = None,
    use_cache: bool = True,
    session_factory=None,
    provider=None,
) -> list[list[float]]:
    """Embed texts in order. `provider` replaces the Gemini call (tests)."""
    context = context or CostContext()
    texts = [t or "" for t in texts]
    if not texts:
        return []
    embed = provider or _provider_embed

    unique = list(dict.fromkeys(texts))
    found: dict[str, list[float]] = {}
    if use_cache:
        from app.discovery.cache import _MISS, get_cached

        for t in unique:
            try:
                hit = await get_cached("embed", text_key(t, task), session_factory=session_factory)
            except Exception:
                hit = _MISS
            if hit is not _MISS and isinstance(hit, list) and len(hit) == EMBEDDING_DIM:
                found[t] = hit

    missing = [t for t in unique if t not in found]
    if missing:
        vectors = await embed(missing, task, context)
        if len(vectors) != len(missing):
            raise EmbeddingUnavailableError(f"expected {len(missing)} embeddings, got {len(vectors)}")
        for t, v in zip(missing, vectors):
            if len(v) != EMBEDDING_DIM:
                raise EmbeddingUnavailableError(f"embedding has {len(v)} dims, expected {EMBEDDING_DIM}")
            found[t] = v
            if use_cache:
                from app.discovery.cache import set_cached

                try:
                    await set_cached("embed", text_key(t, task), v, CACHE_TTL, session_factory=session_factory)
                except Exception:
                    pass
    return [found[t] for t in texts]

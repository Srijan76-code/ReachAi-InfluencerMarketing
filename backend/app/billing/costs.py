"""Cost logging for every paid external call (spec §5.2, CLAUDE.md rule 6).

Callers pass a `CostContext` so costs can be summed per user, campaign and run.
Logging never raises: a failed write is logged and the caller carries on.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CostContext:
    user_id: Optional[str] = None
    campaign_id: Optional[str] = None
    run_id: Optional[str] = None


@dataclass(frozen=True)
class CostRecord:
    provider: str
    sku: str
    context: CostContext
    route: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    units: Optional[int] = None
    usd: Optional[Decimal] = None
    meta: Optional[dict[str, Any]] = None


def token_cost(
    input_tokens: Optional[int],
    output_tokens: Optional[int],
    price_in_per_m: Optional[float],
    price_out_per_m: Optional[float],
) -> Optional[Decimal]:
    """USD cost from token counts and per-million prices. None if any price is unknown."""
    if price_in_per_m is None or price_out_per_m is None:
        return None
    total = (Decimal(input_tokens or 0) * Decimal(str(price_in_per_m))
             + Decimal(output_tokens or 0) * Decimal(str(price_out_per_m))) / Decimal(1_000_000)
    return total.quantize(Decimal("0.000001"))


async def _db_sink(record: CostRecord) -> None:
    from app.db.database import AsyncSessionLocal
    from app.models.cost_event import CostEvent

    async with AsyncSessionLocal() as session:
        session.add(
            CostEvent(
                user_id=record.context.user_id,
                campaign_id=record.context.campaign_id,
                run_id=record.context.run_id,
                provider=record.provider,
                sku=record.sku,
                route=record.route,
                input_tokens=record.input_tokens,
                output_tokens=record.output_tokens,
                units=record.units,
                usd=record.usd,
                meta=record.meta,
            )
        )
        await session.commit()


_sink: Callable[[CostRecord], Awaitable[None]] = _db_sink


def set_sink(sink: Callable[[CostRecord], Awaitable[None]]) -> Callable[[CostRecord], Awaitable[None]]:
    """Replace where cost records go (tests use an in-memory list). Returns the previous sink."""
    global _sink
    previous, _sink = _sink, sink
    return previous


async def record_cost(record: CostRecord) -> None:
    try:
        await _sink(record)
    except Exception:  # cost logging must never break the call it measures
        logger.exception("Failed to record cost event for %s/%s", record.provider, record.sku)

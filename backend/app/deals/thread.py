"""The negotiation so far, in code's words (numbers from our own records only), as context for Jev when it
reads a creator's reply (spec §8.7)."""

from __future__ import annotations

from typing import Optional


def thread_context(events, quoted_rate: Optional[float]) -> Optional[dict]:
    """`events`: the deal's DealEvent rows (any order)."""
    rows = sorted(events, key=lambda e: e.created_at or 0)
    sent = [e for e in rows if e.type == "message_sent" and (e.payload or {}).get("amounts")]
    if not sent and quoted_rate is None:
        return None
    out: dict = {"round": len(sent) + 1}
    if sent:
        a = sent[-1].payload["amounts"]
        out["our_last_offer"] = (f"${a['base']:,} fee plus {a.get('commission_pct')}% commission" if a.get("base")
                                 else f"${(a.get('price') or a.get('counter')):,}")
    if quoted_rate is not None:
        out["their_last_ask"] = f"${quoted_rate:,.0f}"
    return out

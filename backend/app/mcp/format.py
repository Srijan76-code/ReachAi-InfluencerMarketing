"""Turns tool data into the markdown every agent shows the same way (spec §15.4).

All numbers arrive here already computed by our code; nothing in this module calculates a
price, score or date. It only lays them out. Text written by creators is escaped, shortened
and kept on one line so it cannot break a table or pass for an instruction.
"""

import re
from typing import Any, Iterable

from mcp_types import CallToolResult, TextContent

from app.mcp import config

_CONTROL = re.compile(r"[\x00-\x1f\x7f]+")
_DASH = "-"


def cell(value: Any, max_len: int = 60) -> str:
    """One safe table cell: single line, pipes escaped, shortened."""
    if value is None or value == "":
        return _DASH
    text = _CONTROL.sub(" ", str(value)).strip().replace("|", "\\|").replace("`", "'")
    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    return text or _DASH


def number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compact(value: Any) -> str:
    """1250000 -> 1.25M, 42000 -> 42K."""
    n = number(value)
    if n is None:
        return _DASH
    for limit, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if abs(n) >= limit:
            return f"{n / limit:.2f}".rstrip("0").rstrip(".") + suffix
    return f"{n:.0f}"


def percent(value: Any) -> str:
    n = number(value)
    return _DASH if n is None else f"{n:.1f}%".replace(".0%", "%")


def dollars(value: Any) -> str:
    n = number(value)
    if n is None:
        return _DASH
    text = f"{n:,.2f}"
    return "$" + (text[:-3] if text.endswith(".00") else text)


def score(value: Any) -> str:
    n = number(value)
    return _DASH if n is None else f"{n:.0f}"


def table(headers: list[str], rows: Iterable[list[str]]) -> str:
    rows = list(rows)
    if not rows:
        return ""
    head = "| " + " | ".join(headers) + " |"
    rule = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([head, rule, *body])


def campaign_link(campaign_id: str, page: str = "leads") -> str:
    return f"{config.app_url()}/campaign/{campaign_id}/{page}"


def creators_table(leads: list[dict[str, Any]], start_rank: int = 1) -> str:
    rows = []
    for i, lead in enumerate(leads, start=start_rank):
        metrics = lead.get("metrics") or {}
        rows.append(
            [
                str(i),
                cell(lead.get("title"), 40),
                compact(lead.get("subscribers")),
                compact(metrics.get("avg_views")),
                percent(metrics.get("engagement_rate")),
                score(lead.get("final_score")),
                cell(lead.get("deal_status"), 20),
                dollars(lead.get("valuation")),
                cell(lead.get("id"), 30),
            ]
        )
    return table(
        ["#", "Creator", "Subscribers", "Avg views", "Engagement", "Score", "Verdict", "Est. value", "Creator ID"],
        rows,
    )


def creators_summary(leads: list[dict[str, Any]]) -> str:
    """One line of headline numbers over ALL leads of a campaign (not just the page shown)."""
    scores = [s for s in (number(lead.get("final_score")) for lead in leads) if s is not None]
    values = [v for v in (number(lead.get("valuation")) for lead in leads) if v is not None]
    strong = sum(1 for lead in leads if str(lead.get("deal_status") or "").lower() == "strong buy")
    parts = [f"{len(leads)} creator{'' if len(leads) == 1 else 's'}", f"{strong} Strong Buy"]
    if scores:
        parts.append(f"average score {sum(scores) / len(scores):.0f}")
    if values:
        parts.append(f"combined est. value {dollars(sum(values))}")
    return " · ".join(parts)


def result(text: str, data: dict[str, Any], is_error: bool = False) -> CallToolResult:
    """Markdown for people, structured data for programs. Always capped in size."""
    if len(text) > config.MAX_TEXT_CHARS:
        text = text[: config.MAX_TEXT_CHARS].rstrip() + "\n\n(Shortened. Ask for the next page or a narrower filter.)"
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structured_content=data,
        is_error=is_error,
    )

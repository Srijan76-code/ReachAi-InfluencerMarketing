"""Discovery graph state (spec §4.14). Kept small on purpose: profiles and posts live in the
creator database; the state carries ids and small score records, so checkpoints stay fast."""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Annotated, Any, Callable, Optional, TypedDict


def merge_dicts(left: Optional[dict], right: Optional[dict]) -> dict:
    return {**(left or {}), **(right or {})}


class ScoreRecord(TypedDict, total=False):
    creator_id: str
    platform: str
    platform_id: str
    display_name: str
    found_via: str
    mode: str
    final_score: float
    fit: float
    health: float
    risk: float
    deal_status: str
    flags: list[str]
    dropped: bool
    drop_reasons: list[str]
    signals: dict  # Jev answers in plain words, for the reason prompt


class DiscoveryState(TypedDict, total=False):
    run_id: str
    campaign_id: str
    brief: dict  # Brief.to_dict()
    strategy: dict  # StrategyOut.model_dump()
    platforms: dict  # {platform: {selected, weight, note, mode, built}}
    db_hits: list[dict]  # [{creator_id, platform, platform_id, similarity}]
    candidates: Annotated[dict, merge_dicts]  # creator_id -> ScoreRecord (from every branch)
    branch_runs: Annotated[list, operator.add]  # [{platform, mode, sourced, fetched, kept, judged}]
    expanded: Annotated[list, operator.add]  # platforms already expanded after a probe
    top: list[str]  # creator_ids of the final top N
    reasons: Annotated[dict, merge_dicts]  # creator_id -> sentence
    warnings: Annotated[list, operator.add]
    final_leads: list[dict]


class BranchState(TypedDict, total=False):
    run_id: str
    brief: dict
    strategy: dict
    platform: str
    mode: str  # full | probe | expand
    db_hits: list[dict]
    refs: list[dict]  # [{platform_id, found_via}]
    measured: list[str]  # creator_ids that passed the gates
    shortlisted: list[str]
    candidates: Annotated[dict, merge_dicts]
    branch_runs: Annotated[list, operator.add]
    warnings: Annotated[list, operator.add]
    stats: dict


class BranchOutput(TypedDict, total=False):
    """What a platform branch hands back to the parent graph (nothing else, so parallel
    branches never write the same parent field)."""

    candidates: Annotated[dict, merge_dicts]
    branch_runs: Annotated[list, operator.add]
    warnings: Annotated[list, operator.add]


class ReasonState(TypedDict, total=False):
    run_id: str
    brief: dict
    creator: dict  # ScoreRecord


@dataclass
class Deps:
    """Everything the graph calls out to. Passed as LangGraph runtime context (not checkpointed)."""

    adapters: dict[str, Callable[[], Any]]  # platform -> factory returning a PlatformAdapter
    session_factory: Any = None
    embed: Optional[Callable] = None  # async (texts, task) -> vectors; default app.llm.embeddings
    judge: Optional[Callable] = None  # async (state, questions) -> Judgment; default app.judge.client.judge
    llm: Optional[Callable] = None  # async (route, prompt, schema) -> model; default app.llm.client.achat
    now: Optional[Callable] = None
    cost_context: Any = None
    extra: dict = field(default_factory=dict)

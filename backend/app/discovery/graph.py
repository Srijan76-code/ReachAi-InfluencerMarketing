"""The discovery graph (spec §4.14).

START -> [strategy | platform_select | db_search]  (parallel)
      -> plan -> Send(platform_branch) per platform  (parallel; full search or a small probe)
      -> merge_rank (waits for all branches)
      -> probe_check: Send(platform_branch, expand) where a probe beats the top list, else Send(reason) per top creator
      -> finalize (waits for all reasons)
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from app.discovery import nodes
from app.discovery.state import BranchOutput, BranchState, Deps, DiscoveryState

API_RETRY = RetryPolicy(max_attempts=3, initial_interval=1.0, backoff_factor=2.0)


def build_branch_graph() -> StateGraph:
    g = StateGraph(BranchState, context_schema=Deps, output_schema=BranchOutput)
    g.add_node("search", nodes.search, retry_policy=API_RETRY)
    g.add_node("fetch_measure", nodes.fetch_measure, retry_policy=API_RETRY)
    g.add_node("shortlist", nodes.shortlist, retry_policy=API_RETRY)
    g.add_node("judge_score", nodes.judge_score, retry_policy=API_RETRY)
    g.add_edge(START, "search")
    g.add_edge("search", "fetch_measure")
    g.add_edge("fetch_measure", "shortlist")
    g.add_edge("shortlist", "judge_score")
    g.add_edge("judge_score", END)
    return g


def build_discovery_graph() -> StateGraph:
    g = StateGraph(DiscoveryState, context_schema=Deps)
    g.add_node("strategy", nodes.strategy, retry_policy=API_RETRY)
    g.add_node("platform_select", nodes.platform_select, retry_policy=API_RETRY)
    g.add_node("db_search", nodes.db_search, retry_policy=API_RETRY)
    g.add_node("plan", nodes.plan)
    g.add_node("platform_branch", build_branch_graph().compile())
    g.add_node("merge_rank", nodes.merge_rank, defer=True)
    g.add_node("reason", nodes.reason, retry_policy=API_RETRY)
    g.add_node("finalize", nodes.finalize, defer=True)

    for first in ("strategy", "platform_select", "db_search"):
        g.add_edge(START, first)
    g.add_edge(["strategy", "platform_select", "db_search"], "plan")  # waits for all three
    g.add_conditional_edges("plan", nodes.fan_out, ["platform_branch", "merge_rank"])
    g.add_edge("platform_branch", "merge_rank")
    g.add_conditional_edges("merge_rank", nodes.probe_check, ["platform_branch", "reason", "finalize"])
    g.add_edge("reason", "finalize")
    g.add_edge("finalize", END)
    return g

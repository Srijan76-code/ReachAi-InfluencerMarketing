from langgraph.cache.memory import InMemoryCache
from langgraph.graph import END, START, StateGraph
from langgraph.types import CachePolicy, RetryPolicy, Send

from app.outreach.state import OutreachState
from app.outreach.nodes import (
    collect_creator_pitch,
    finalize_pitch_pack,
    generate_creator_pitch,
    prepare_pitch_batch,
    repair_creator_pitch,
    validate_creator_pitch,
)
from app.outreach.utils import pitch_cache_key


def _fan_out(state: OutreachState):
    return [
        Send(
            "generate_creator_pitch",
            {
                "outreach_job_id": state.get("outreach_job_id"),
                "campaign_id": state.get("campaign_id"),
                "creator_input": item,
            },
        )
        for item in state.get("work_items", [])
    ]


def _validation_route(state: OutreachState) -> str:
    if state.get("validation_passed"):
        return "collect_creator_pitch"
    if (state.get("repair_count") or 0) < 1:
        return "repair_creator_pitch"
    return "collect_creator_pitch"


def build_outreach_graph() -> StateGraph:
    graph = StateGraph(OutreachState)
    graph.add_node("prepare_pitch_batch", prepare_pitch_batch)
    graph.add_node(
        "generate_creator_pitch",
        generate_creator_pitch,
        retry_policy=RetryPolicy(),
        cache_policy=CachePolicy(key_func=pitch_cache_key, ttl=3600),
    )
    graph.add_node("validate_creator_pitch", validate_creator_pitch)
    graph.add_node(
        "repair_creator_pitch",
        repair_creator_pitch,
        retry_policy=RetryPolicy(),
        cache_policy=CachePolicy(key_func=pitch_cache_key, ttl=3600),
    )
    graph.add_node("collect_creator_pitch", collect_creator_pitch)
    graph.add_node("finalize_pitch_pack", finalize_pitch_pack, defer=True)

    graph.add_edge(START, "prepare_pitch_batch")
    graph.add_conditional_edges("prepare_pitch_batch", _fan_out)
    graph.add_edge("generate_creator_pitch", "validate_creator_pitch")
    graph.add_conditional_edges(
        "validate_creator_pitch",
        _validation_route,
        {
            "repair_creator_pitch": "repair_creator_pitch",
            "collect_creator_pitch": "collect_creator_pitch",
        },
    )
    graph.add_edge("repair_creator_pitch", "validate_creator_pitch")
    graph.add_edge("collect_creator_pitch", "finalize_pitch_pack")
    graph.add_edge("finalize_pitch_pack", END)
    return graph
import asyncio

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, Send

from app.outreach import graph as outreach_graph
from app.outreach.graph import build_outreach_graph
from app.outreach.utils import current_creator_input


def _creator(creator_id: str) -> dict:
    return {
        "id": creator_id,
        "title": creator_id,
        "description": "Real lead snapshot used by the test harness.",
        "socials": {"instagram": f"https://instagram.com/{creator_id}"},
        "recent_videos": [{"title": f"{creator_id} project"}],
        "llm_reasoning": f"{creator_id} creator reasoning",
    }


def test_real_graph_fanout_keeps_two_creator_branches_isolated(monkeypatch):
    async def fake_generate(state):
        creator_input = current_creator_input(state)
        creator_id = creator_input["creator_id"]
        bundle = {
            "creator_id": creator_id,
            "pitch_angle": creator_id,
            "personalization": [{"evidence_id": "video_1", "reason": creator_id}],
            "instagram": {"body": creator_id},
        }
        return Command(
            update={
                "creator_inputs": {creator_id: creator_input},
                "creator_pitch_bundles": {
                    creator_id: bundle,
                },
                "creator_repair_counts": {creator_id: 0},
            },
            goto=Send("validate_creator_pitch", {"creator_input": creator_input, "creator_pitch_bundles": {creator_id: bundle}}),
        )

    async def fake_validate(state):
        creator_id = current_creator_input(state)["creator_id"]
        validation = {creator_id: {"errors": [], "passed": True}}
        bundle = (state.get("creator_pitch_bundles") or {}).get(creator_id, {})
        return Command(
            update={"creator_validations": validation},
            goto=Send("collect_creator_pitch", {"creator_input": current_creator_input(state), "creator_pitch_bundles": {creator_id: bundle}, "creator_validations": validation}),
        )

    monkeypatch.setattr(outreach_graph, "generate_creator_pitch", fake_generate)
    monkeypatch.setattr(outreach_graph, "validate_creator_pitch", fake_validate)
    workflow = build_outreach_graph().compile(checkpointer=InMemorySaver())
    state = {
        "outreach_job_id": "batch-test",
        "campaign_id": "campaign",
        "campaign_context": {"brand": {"name": "DataLaunch"}},
        "selected_creators": [_creator("creator-a"), _creator("creator-b")],
        "default_collaboration": {"type": "affiliate"},
        "default_deliverables": ["one Instagram story"],
    }
    result = asyncio.run(workflow.ainvoke(state, config={"configurable": {"thread_id": "batch-test"}}))
    results = sorted(result["pitch_results"], key=lambda item: item["selection_index"])
    assert [item["creator_id"] for item in results] == ["creator-a", "creator-b"]
    assert [item["pitch_bundle"]["creator_id"] for item in results] == ["creator-a", "creator-b"]

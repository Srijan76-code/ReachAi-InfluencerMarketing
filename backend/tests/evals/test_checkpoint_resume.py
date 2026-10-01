import asyncio

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, Send

from app.outreach import graph as outreach_graph
from app.outreach.graph import build_outreach_graph


def _creator(creator_id: str, name: str) -> dict:
    return {
        "id": creator_id,
        "title": name,
        "description": "AI educator",
        "socials": {"instagram": f"https://instagram.com/{creator_id}"},
        "recent_videos": [{"title": f"{name} ML project", "views": 1000}],
        "llm_reasoning": f"{name} teaches practical ML.",
    }


def _state() -> dict:
    return {
        "outreach_job_id": "resume-test",
        "campaign_id": "campaign",
        "campaign_context": {
            "brand": {"name": "DataLaunch", "core_outcome": "AI courses"},
            "campaign": {"goal": "reach learners"},
        },
        "selected_creators": [_creator("creator-a", "Creator A")],
        "default_collaboration": {"type": "affiliate"},
        "default_deliverables": ["one Instagram story"],
    }


def test_checkpoint_resume_keeps_completed_branch(monkeypatch):
    attempts = {"creator-a": 0}
    fail_first_attempt = True

    async def fake_generate(state):
        nonlocal fail_first_attempt
        from app.outreach.utils import current_creator_input

        creator_input = current_creator_input(state)
        creator_id = creator_input["creator_id"]
        attempts[creator_id] += 1
        if fail_first_attempt:
            raise RuntimeError("intentional branch failure")
        bundle = {
            "creator_id": creator_id,
            "pitch_angle": f"{creator_input['creator_identity']['name']} angle",
            "personalization": [{"evidence_id": "video_1", "reason": "Recent ML project"}],
            "instagram": {"body": f"{creator_input['creator_identity']['name']} DataLaunch affiliate one Instagram story?"},
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
        from app.outreach.utils import current_creator_input

        creator_id = current_creator_input(state)["creator_id"]
        validation = {creator_id: {"errors": [], "passed": True}}
        bundle = (state.get("creator_pitch_bundles") or {}).get(creator_id, {})
        return Command(
            update={"creator_validations": validation},
            goto=Send("collect_creator_pitch", {"creator_input": current_creator_input(state), "creator_pitch_bundles": {creator_id: bundle}, "creator_validations": validation}),
        )

    monkeypatch.setattr(outreach_graph, "generate_creator_pitch", fake_generate)
    monkeypatch.setattr(outreach_graph, "validate_creator_pitch", fake_validate)
    checkpointer = InMemorySaver()
    workflow = build_outreach_graph().compile(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "resume-test"}}

    async def run_first():
        try:
            await workflow.ainvoke(_state(), config=config)
        except RuntimeError:
            return
        raise AssertionError("the test branch should fail")

    asyncio.run(run_first())
    assert attempts["creator-a"] >= 1

    fail_first_attempt = False
    result = asyncio.run(workflow.ainvoke(_state(), config=config))
    assert {item["creator_id"] for item in result["pitch_results"]} == {"creator-a"}
    assert attempts["creator-a"] > 1

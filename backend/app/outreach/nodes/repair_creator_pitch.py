import json

from app.llm.client import achat
from langgraph.types import Command, Send
from app.outreach.nodes.generate_creator_pitch import AI_FAILED, _generation_prompt
from app.schemas.outreach import PitchBundle
from app.outreach.state import OutreachState
from app.outreach.utils import current_creator_input, cost_context


async def repair_creator_pitch(state: OutreachState) -> OutreachState:
    creator_input = current_creator_input(state)
    creator_id = creator_input.get("creator_id", "")
    validation = (state.get("creator_validations") or {}).get(creator_id, {})
    prompt = f"""
Repair this creator outreach PitchBundle. Return the complete corrected PitchBundle.
Make only the changes required by the validation errors. Preserve valid content.
Use only the available channels and evidence from the original creator input.

ORIGINAL GENERATION INSTRUCTIONS:
{_generation_prompt(creator_input)}

CURRENT PITCH:
{json.dumps((state.get("creator_pitch_bundles") or {}).get(creator_id, {}), default=str)}

VALIDATION ERRORS:
{json.dumps(validation.get("errors") or [], default=str)}
""".strip()
    repair_count = (state.get("creator_repair_counts") or {}).get(creator_id, 0) + 1
    try:
        bundle = await achat("pitch", prompt, PitchBundle, context=cost_context(state))
    except Exception:  # noqa: BLE001 - keep the first draft (flagged for review) instead of failing the batch
        current = (state.get("creator_pitch_bundles") or {}).get(creator_id, {})
        validation = {creator_id: {"errors": list(validation.get("errors") or []) + [AI_FAILED], "passed": False}}
        return Command(update={"creator_validations": validation}, goto=Send("collect_creator_pitch", {
            "outreach_job_id": state.get("outreach_job_id"), "campaign_id": state.get("campaign_id"),
            "creator_input": creator_input, "creator_pitch_bundles": {creator_id: current},
            "creator_validations": validation, "creator_repair_counts": {creator_id: repair_count}}))
    repaired_bundle = bundle.model_dump()
    return Command(
        update={
        "creator_pitch_bundles": {creator_id: bundle.model_dump()},
        "creator_repair_counts": {creator_id: repair_count},
        },
        goto=Send(
            "validate_creator_pitch",
            {
                # keep the job and campaign ids: the next steps log their AI costs against them (rule 6)
                "outreach_job_id": state.get("outreach_job_id"),
                "campaign_id": state.get("campaign_id"),
                "creator_input": creator_input,
                "creator_pitch_bundles": {creator_id: repaired_bundle},
                "creator_repair_counts": {creator_id: repair_count},
            },
        ),
    )
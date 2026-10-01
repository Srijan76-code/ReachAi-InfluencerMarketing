import asyncio
import json

from app.core.model import model
from langgraph.types import Command, Send
from app.outreach.nodes.generate_creator_pitch import _generation_prompt
from app.schemas.outreach import PitchBundle
from app.outreach.state import OutreachState
from app.outreach.utils import current_creator_input


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
    structured_llm = model.with_structured_output(PitchBundle)
    result = await asyncio.to_thread(structured_llm.invoke, prompt)
    bundle = result if isinstance(result, PitchBundle) else PitchBundle.model_validate(result)
    repaired_bundle = bundle.model_dump()
    repair_count = (state.get("creator_repair_counts") or {}).get(creator_id, 0) + 1
    return Command(
        update={
        "creator_pitch_bundles": {creator_id: bundle.model_dump()},
        "creator_repair_counts": {creator_id: repair_count},
        },
        goto=Send(
            "validate_creator_pitch",
            {
                "creator_input": creator_input,
                "creator_pitch_bundles": {creator_id: repaired_bundle},
                "creator_repair_counts": {creator_id: repair_count},
            },
        ),
    )
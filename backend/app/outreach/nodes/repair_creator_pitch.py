import asyncio
import json

from app.core.model import model
from app.outreach.nodes.generate_creator_pitch import _generation_prompt
from app.schemas.outreach import PitchBundle
from app.outreach.state import OutreachState


async def repair_creator_pitch(state: OutreachState) -> OutreachState:
    creator_input = state.get("creator_input") or {}
    prompt = f"""
Repair this creator outreach PitchBundle. Return the complete corrected PitchBundle.
Make only the changes required by the validation errors. Preserve valid content.
Use only the available channels and evidence from the original creator input.

ORIGINAL GENERATION INSTRUCTIONS:
{_generation_prompt(creator_input)}

CURRENT PITCH:
{json.dumps(state.get("pitch_bundle") or {}, default=str)}

VALIDATION ERRORS:
{json.dumps(state.get("validation_errors") or [], default=str)}
""".strip()
    structured_llm = model.with_structured_output(PitchBundle)
    result = await asyncio.to_thread(structured_llm.invoke, prompt)
    bundle = result if isinstance(result, PitchBundle) else PitchBundle.model_validate(result)
    return {
        "pitch_bundle": bundle.model_dump(),
        "repair_count": (state.get("repair_count") or 0) + 1,
    }
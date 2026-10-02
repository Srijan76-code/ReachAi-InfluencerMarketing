import asyncio
import json

from app.core.model import model
from langgraph.types import Command, Send

from app.outreach.state import OutreachState
from app.outreach.utils import current_creator_input
from app.schemas.outreach import PitchBundle


def _generation_prompt(creator_input: dict) -> str:
    campaign = creator_input.get("campaign_context") or {}
    brand = campaign.get("brand") or {}
    audience = campaign.get("audience") or {}
    campaign_details = campaign.get("campaign") or {}
    available = creator_input.get("available_channels") or []
    return f"""
You write a personalized creator outreach pitch pack for Reach AI.

Return exactly one structured PitchBundle for this creator.
Generate content only for these available channels: {json.dumps(available)}.
Set every unavailable channel to null.

Required pitch structure:
1. Specific creator observation grounded in evidence.
2. Why it connects to the campaign.
3. What the brand proposes.
4. Collaboration type and deliverables.
5. A low-friction call to action.

Rules:
- Use the exact creator_id from input.
- Use only evidence_id values supplied in evidence.
- Mention the brand naturally and never mention internal scores, valuation, or risk fields.
- Ask no more than two questions in the complete bundle.
- Do not invent contact details, audience claims, performance, or creator facts.
- Keep email concise and social messages channel-appropriate.

CAMPAIGN:
{json.dumps({"brand": brand, "audience": audience, "campaign": campaign_details, "topics": campaign.get("content_topics", []), "pain_points": campaign.get("pain_points", []), "primary_metric": campaign.get("primary_metric"), "safety_level": campaign.get("safety_level")}, default=str)}

COLLABORATION:
{json.dumps({"collaboration": creator_input.get("collaboration"), "deliverables": creator_input.get("deliverables", [])}, default=str)}

CREATOR:
{json.dumps({"identity": creator_input.get("creator_identity"), "description": creator_input.get("creator_description"), "rich_context": creator_input.get("rich_context"), "recent_videos": creator_input.get("recent_videos"), "fit_reasoning": creator_input.get("fit_reasoning"), "evidence": creator_input.get("evidence")}, default=str)}
""".strip()


async def generate_creator_pitch(state: OutreachState) -> OutreachState:
    creator_input = current_creator_input(state)
    structured_llm = model.with_structured_output(PitchBundle)
    result = await asyncio.to_thread(structured_llm.invoke, _generation_prompt(creator_input))
    bundle = result if isinstance(result, PitchBundle) else PitchBundle.model_validate(result)
    bundle_data = bundle.model_dump()
    return Command(
        update={
        "creator_inputs": {creator_input.get("creator_id", ""): creator_input},
        "creator_pitch_bundles": {creator_input.get("creator_id", ""): bundle_data},
        "creator_repair_counts": {creator_input.get("creator_id", ""): 0},
        },
        goto=Send(
            "validate_creator_pitch",
            {
                "creator_input": creator_input,
                "creator_pitch_bundles": {creator_input.get("creator_id", ""): bundle_data},
            },
        ),
    )
import json

from app.llm.client import achat
from langgraph.types import Command, Send

from app.outreach.state import OutreachState
from app.outreach.utils import current_creator_input, cost_context
from app.schemas.outreach import PitchBundle


def _generation_prompt(creator_input: dict) -> str:
    campaign = creator_input.get("campaign_context") or {}
    brand = campaign.get("brand") or {}
    audience = campaign.get("audience") or {}
    campaign_details = campaign.get("campaign") or {}
    available = creator_input.get("available_channels") or []
    collab = creator_input.get("collaboration") or {}
    raw_collab = str(collab.get("type") or "partnership")
    human_collab = raw_collab.replace("_", " ")
    deliverables = creator_input.get("deliverables") or []

    return f"""
You write a personalized, authentic creator outreach pitch pack for Reach AI.
Your goal is high creator response rates. Sound like an experienced, thoughtful human brand partnerships manager — NOT an AI bot.

Return exactly one structured PitchBundle for this creator.
Generate content only for these available channels: {json.dumps(available)}.
Set every unavailable channel to null.

Tone & Style Rules (CRITICAL):
1. NO AI Clichés & NO Formulaic Openers:
   - NEVER start with robotic formulas like "I loved your guide in '[Exact Video Title]' and how you help...", "Hope this email finds you well", or "I stumbled upon your channel".
   - Instead, open naturally by casually referencing their specific niche, expertise, or a recent topic they covered (e.g., "Loved your recent breakdown on tech career paths", "Saw your walkthrough on...").
2. NO Snake_Case or Internal Enums:
   - NEVER say '{raw_collab}', use underscores, or expose a campaign/package label. Refer to the ask simply as a "collaboration" or "partnership".
3. Keep Package Details Internal:
   - NEVER mention deliverables, runtimes, placements, pinned comments, description links, or quantities in the email or DM. Those are deal-setup details, not a first outreach message.
   - Do not say "sponsored video" or "integration". Make the initial ask feel personal and low-pressure: invite the creator to explore a potential collaboration.
4. High-Converting Structure:
   - Paragraph 1: Genuine, authentic observation about their content and why their perspective resonated.
   - Paragraph 2: Brief 1-2 sentence intro of {brand.get('name', 'the brand')} and why it provides real value to their specific audience.
   - Paragraph 3: A simple, low-friction collaboration invitation (e.g., "Would you be open to exploring a potential collaboration?").
5. Formatting & Constraints:
   - Email: Concise, 3 short paragraphs max. Subject line must look like a personal 1-on-1 note, not marketing spam.
   - Social DMs (IG/Twitter): 2-4 punchy, conversational sentences max.
   - Use the exact creator_id from input.
   - Use only evidence_id values supplied in evidence.
   - Mention the brand naturally and never mention internal scores, valuation, or risk fields.
   - Maximum 2 questions across the entire bundle.

CAMPAIGN DETAILS:
{json.dumps({"brand": brand, "audience": audience, "campaign": campaign_details, "topics": campaign.get("content_topics", []), "pain_points": campaign.get("pain_points", [])}, default=str)}

PROPOSED COLLABORATION:
Type: {human_collab}
Deliverables: {json.dumps(deliverables)}

CREATOR CONTEXT & EVIDENCE:
{json.dumps({"identity": creator_input.get("creator_identity"), "description": creator_input.get("creator_description"), "rich_context": creator_input.get("rich_context"), "recent_videos": creator_input.get("recent_videos"), "fit_reasoning": creator_input.get("fit_reasoning"), "evidence": creator_input.get("evidence")}, default=str)}
""".strip()


async def generate_creator_pitch(state: OutreachState) -> OutreachState:
    creator_input = current_creator_input(state)
    bundle = await achat("pitch", _generation_prompt(creator_input), PitchBundle, context=cost_context(state))
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
                "outreach_job_id": state.get("outreach_job_id"),
                "campaign_id": state.get("campaign_id"),
                "creator_input": creator_input,
                "creator_pitch_bundles": {creator_input.get("creator_id", ""): bundle_data},
            },
        ),
    )

import re

from pydantic import ValidationError
from langgraph.types import Command, Send

from app.schemas.outreach import PitchBundle
from app.outreach.state import CreatorPitchInput, OutreachState
from app.outreach.utils import current_creator_input


CHANNEL_FIELDS = {
    "email": "email",
    "instagram": "instagram",
    "twitter": "twitter",
    "linkedin": "linkedin",
}
INTERNAL_TERMS = ("final_score", "semantic_score", "health_score", "trust_score", "valuation", "risk_penalty", "deal_status")


def _bundle_text(bundle: dict) -> str:
    parts = [str(bundle.get("pitch_angle", ""))]
    for item in bundle.get("personalization", []):
        parts.extend([str(item.get("evidence_id", "")), str(item.get("reason", ""))])
    for field in CHANNEL_FIELDS.values():
        channel = bundle.get(field)
        if channel:
            parts.extend(str(value) for value in channel.values())
    return "\n".join(parts)


def validate_bundle(bundle_data: dict, creator_input: CreatorPitchInput) -> list[str]:
    errors: list[str] = []
    try:
        bundle = PitchBundle.model_validate(bundle_data)
    except ValidationError as exc:
        return [f"schema: {error['msg']}" for error in exc.errors()]

    creator_id = str(creator_input.get("creator_id", ""))
    if bundle.creator_id != creator_id:
        errors.append("creator_id does not match the selected creator")

    available = set(creator_input.get("available_channels") or [])
    for channel, field in CHANNEL_FIELDS.items():
        value = getattr(bundle, field)
        if channel in available and value is None:
            errors.append(f"missing pitch for available channel: {channel}")
        if channel not in available and value is not None:
            errors.append(f"pitch generated for unavailable channel: {channel}")

    evidence_ids = {str(item.get("evidence_id")) for item in creator_input.get("evidence") or []}
    for item in bundle.personalization:
        if item.evidence_id not in evidence_ids:
            errors.append(f"unsupported evidence_id: {item.evidence_id}")

    text = _bundle_text(bundle.model_dump())
    text_lower = text.lower()
    brand_name = str((creator_input.get("campaign_context") or {}).get("brand", {}).get("name") or "").strip()
    creator_name = str((creator_input.get("creator_identity") or {}).get("name") or "").strip()
    collaboration_type = str((creator_input.get("collaboration") or {}).get("type") or "").strip()
    if brand_name and brand_name.lower() not in text_lower:
        errors.append("brand name is missing from the pitch")
    if creator_name and creator_name.lower() != "unknown creator" and creator_name.lower() not in text_lower:
        errors.append("creator name is missing from the pitch")
    if collaboration_type and collaboration_type.lower() not in text_lower:
        errors.append("collaboration type is missing from the pitch")
    for deliverable in creator_input.get("deliverables") or []:
        if str(deliverable).lower() not in text_lower:
            errors.append(f"deliverable is missing from the pitch: {deliverable}")
    for term in INTERNAL_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", text_lower):
            errors.append(f"internal scoring field exposed: {term}")
    if text.count("?") > 2:
        errors.append("pitch contains more than two questions")
    if not bundle.personalization:
        errors.append("at least one evidence-backed personalization item is required")
    return errors


async def validate_creator_pitch(state: OutreachState) -> OutreachState:
    creator_input = current_creator_input(state)
    creator_id = creator_input.get("creator_id", "")
    bundle = (state.get("creator_pitch_bundles") or {}).get(creator_id, {})
    errors = validate_bundle(bundle, creator_input)
    validation = {creator_id: {"errors": errors, "passed": not errors}}
    repair_count = (state.get("creator_repair_counts") or {}).get(creator_id, 0)
    destination = "collect_creator_pitch" if not errors or repair_count >= 1 else "repair_creator_pitch"
    return Command(
        update={"creator_validations": validation},
        goto=Send(
            destination,
            {
                "creator_input": creator_input,
                "creator_pitch_bundles": {creator_id: bundle},
                "creator_validations": validation,
                "creator_repair_counts": {creator_id: repair_count},
            },
        ),
    )
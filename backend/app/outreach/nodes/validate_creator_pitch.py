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
PACKAGE_DETAIL_PATTERNS = (
    (r"\b\d+x\s*\d+\s*(?:s|sec|secs|second|seconds)\b", "a duration/quantity"),
    (r"\b(?:pre|mid)[-\s]?roll\b", "a placement"),
    (r"\bsponsored video\b", "a campaign format"),
    (r"\b(?:paid )?integration\b", "a campaign format"),
    (r"\bpinned comment\b", "a pinned comment"),
    (r"\b(?:top )?description link\b", "a description link"),
    (r"\bdeliverables?\b", "deliverables"),
)
FORMULAIC_OPENERS = (
    "i loved your guide in",
    "i loved your video in",
    "hope this email finds you well",
    "i stumbled upon your channel",
)


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

    if brand_name and brand_name.lower() not in text_lower:
        errors.append("brand name is missing from the pitch")
    if creator_name and creator_name.lower() != "unknown creator" and creator_name.lower() not in text_lower:
        errors.append("creator name is missing from the pitch")
    if (creator_input.get("collaboration") or {}).get("type") and not any(
        phrase in text_lower for phrase in ("collaboration", "partnership", "work together")
    ):
        errors.append("pitch does not include a clear collaboration invitation")

    for raw_enum in ("sponsored_video", "dedicated_video", "product_placement", "shoutout_mention"):
        if raw_enum in text_lower:
            errors.append(f"do not use raw snake_case enum '{raw_enum}' in copy")

    for pattern, description in PACKAGE_DETAIL_PATTERNS:
        if re.search(pattern, text_lower):
            errors.append(f"pitch exposes internal package detail: {description}")
    for opener in FORMULAIC_OPENERS:
        if opener in text_lower:
            errors.append(f"pitch uses formulaic opener: '{opener}'")

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
                "outreach_job_id": state.get("outreach_job_id"),
                "campaign_id": state.get("campaign_id"),
                "creator_input": creator_input,
                "creator_pitch_bundles": {creator_id: bundle},
                "creator_validations": validation,
                "creator_repair_counts": {creator_id: repair_count},
            },
        ),
    )

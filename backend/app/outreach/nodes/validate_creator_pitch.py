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

# What a first message must never contain (spec §7.4): money is agreed later in the chat, links other than the
# brand's own site look like spam or come from untrusted creator text, contact details and phone numbers come
# from the founder's Gmail, and template leftovers or AI phrases give the message away.
MONEY = re.compile(
    r"[$€£₹]\s?\d|\b\d[\d,]*(?:\.\d+)?\s?(?:usd|eur|gbp|inr|dollars?|bucks|rupees?)\b|\b(?:rs\.?|inr|usd)\s?\d"
    r"|\b\d+(?:\.\d+)?\s?k\b",
    re.I,
)
URL = re.compile(r"\b(?:https?://|www\.)[^\s<>()\"']+|\b[a-z0-9-]+\.(?:ly|gl|io|co|com|net|me|app|link)/[^\s<>()\"']*", re.I)
EMAIL_ADDR = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PHONE = re.compile(r"(?<![\w$€£₹])\+?\d[\d\s().-]{8,}\d\b")
PLACEHOLDER = re.compile(r"\[[^\]\n]{2,40}\]|\{[^}\n]{2,40}\}|<<?[a-z_ ]{3,30}>>?", re.I)
AI_TELLS = ("as an ai", "language model", "ignore previous", "ignore all previous", "system prompt",
            "as instructed", "i cannot help", "i can't help with")
MAX_SUBJECT_CHARS = 80
MAX_EMAIL_CHARS = 1500
MAX_DM_CHARS = 600


def _name_forms(name: str) -> list[str]:
    """Ways the pitch may write the creator's name: the full name, or its first word ("Sofia ♡" → "sofia",
    "Sofia | Tech & AI" → "sofia", "@sofia.codes" → "sofia.codes"). Empty when the name has no letters."""
    clean = re.sub(r"[^\w\s.'-]", " ", name.replace("@", " ")).strip().lower()
    words = [w.strip(".'-") for w in clean.split() if len(w.strip(".'-")) >= 2]
    if not words:
        return []
    forms = {clean, words[0]}
    forms.update(p for p in re.split(r"[._-]", words[0]) if len(p) >= 3)
    return [f for f in forms if f]


def _host(url: str) -> str:
    u = re.sub(r"^(?:https?://)?(?:www\.)?", "", url.lower())
    return u.split("/", 1)[0].split("?", 1)[0]


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
    first_name = str((creator_input.get("creator_identity") or {}).get("first_name") or "").strip()
    forms = _name_forms(creator_name) if creator_name.lower() != "unknown creator" else []
    if forms and first_name:
        forms = [*forms, first_name.lower()]
    if forms and not any(re.search(rf"(?<!\w){re.escape(f)}(?!\w)", text_lower) for f in forms):
        errors.append("creator name is missing from the pitch")

    # message text only (not the internal angle/reasons): what the creator would actually read
    message = "\n".join(str(v) for f in CHANNEL_FIELDS.values() if (ch := bundle_data.get(f)) and isinstance(ch, dict)
                        for v in ch.values() if v)
    brand_site = _host(str((creator_input.get("campaign_context") or {}).get("brand", {}).get("website") or ""))
    links = URL.findall(message)
    if any(not brand_site or _host(u) != brand_site for u in links):
        errors.append("pitch links to a site other than the brand's own website")
    no_links = URL.sub(" ", message)
    if MONEY.search(no_links):
        errors.append("pitch mentions money: prices are agreed later in the chat")
    if EMAIL_ADDR.search(no_links):
        errors.append("pitch contains an email address")
    if PHONE.search(no_links):
        errors.append("pitch contains a phone number")
    if PLACEHOLDER.search(message):
        errors.append("pitch contains a template placeholder")
    lower_message = message.lower()
    for tell in AI_TELLS:
        if tell in lower_message:
            errors.append(f"pitch contains AI or instruction text: '{tell}'")

    email = bundle_data.get("email") if isinstance(bundle_data.get("email"), dict) else None
    if email is not None:
        subject, body = str(email.get("subject") or "").strip(), str(email.get("body") or "").strip()
        if not body:
            errors.append("email body is empty")
        elif len(body) > MAX_EMAIL_CHARS:
            errors.append(f"email is too long (over {MAX_EMAIL_CHARS} characters)")
        if not subject:
            errors.append("email subject is empty")
        elif len(subject) > MAX_SUBJECT_CHARS:
            errors.append(f"email subject is too long (over {MAX_SUBJECT_CHARS} characters)")
    for f in ("instagram", "twitter", "linkedin"):
        dm = bundle_data.get(f)
        if isinstance(dm, dict):
            body = str(dm.get("body") or "").strip()
            if not body:
                errors.append(f"{f} message is empty")
            elif len(body) > MAX_DM_CHARS:
                errors.append(f"{f} message is too long (over {MAX_DM_CHARS} characters)")
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
    if URL.sub(" ", text).count("?") > 2:
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

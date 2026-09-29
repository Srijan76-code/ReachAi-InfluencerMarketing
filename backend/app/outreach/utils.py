import hashlib
import json
from typing import Any, Dict, List


PROMPT_VERSION = "outreach-pitch-v1"
CHANNEL_KEYS = ("email", "instagram", "twitter", "linkedin")


def json_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def available_channels(creator: Dict[str, Any]) -> List[str]:
    socials = creator.get("socials") or creator.get("social_links") or {}
    return [channel for channel in CHANNEL_KEYS if socials.get(channel)]


def creator_name(creator: Dict[str, Any]) -> str:
    rich_context = creator.get("rich_context")
    rich_name = rich_context.get("channel_name") if isinstance(rich_context, dict) else None
    return str(creator.get("title") or creator.get("name") or rich_name or "Unknown creator")


def creator_evidence(creator: Dict[str, Any]) -> List[Dict[str, Any]]:
    evidence: List[Dict[str, Any]] = []
    videos = creator.get("recent_videos") or []
    for index, video in enumerate(videos[:8], start=1):
        if isinstance(video, dict):
            title = video.get("title") or "Untitled video"
            views = video.get("views")
        else:
            title = str(video)
            views = None
        evidence.append({"evidence_id": f"video_{index}", "title": title, "views": views})

    reasoning = creator.get("llm_reasoning") or creator.get("fit_reasoning")
    if reasoning:
        evidence.append({"evidence_id": "creator_reasoning", "reason": str(reasoning)})
    return evidence


def cache_key_for_input(
    *,
    campaign_context: Dict[str, Any],
    creator_input: Dict[str, Any],
    collaboration: Dict[str, Any],
    deliverables: List[str],
    model_name: str,
) -> str:
    return json_hash(
        {
            "prompt_version": PROMPT_VERSION,
            "model": model_name,
            "campaign_context": campaign_context,
            "creator": creator_input,
            "collaboration": collaboration,
            "deliverables": deliverables,
        }
    )


def pitch_cache_key(state: Dict[str, Any]) -> str:
    return state.get("cache_key") or json_hash(state)
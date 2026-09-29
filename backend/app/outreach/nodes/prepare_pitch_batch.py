from app.outreach.state import OutreachState
from app.outreach.utils import available_channels, cache_key_for_input, creator_evidence, creator_name, PROMPT_VERSION


async def prepare_pitch_batch(state: OutreachState) -> OutreachState:
    campaign_context = state.get("campaign_context") or {}
    default_collaboration = state.get("default_collaboration") or {}
    default_deliverables = state.get("default_deliverables") or []
    creator_overrides = state.get("creator_overrides") or {}
    work_items = []

    for selection_index, creator in enumerate(state.get("selected_creators") or []):
        creator_id = str(creator.get("id") or creator.get("creator_id") or "")
        override = creator_overrides.get(creator_id) or {}
        collaboration_type = override.get("collaboration_type") or default_collaboration.get("type")
        deliverables = override.get("deliverables") or default_deliverables
        socials = creator.get("socials") or creator.get("social_links") or {}
        creator_input = {
            "creator_id": creator_id,
            "selection_index": selection_index,
            "campaign_context": campaign_context,
            "collaboration": {"type": collaboration_type},
            "deliverables": list(deliverables),
            "creator_identity": {
                "name": creator_name(creator),
                "country": creator.get("country"),
                "channel_id": creator.get("id"),
            },
            "creator_description": creator.get("description", ""),
            "rich_context": creator.get("rich_context", ""),
            "recent_videos": creator.get("recent_videos") or [],
            "fit_reasoning": creator.get("llm_reasoning") or creator.get("fit_reasoning", ""),
            "relevance_score": creator.get("relevance_score"),
            "available_channels": available_channels(creator),
            "social_links": socials,
            "evidence": creator_evidence(creator),
        }
        creator_input["cache_key"] = cache_key_for_input(
            campaign_context=campaign_context,
            creator_input=creator_input,
            collaboration=creator_input["collaboration"],
            deliverables=creator_input["deliverables"],
            model_name=state.get("model_name", "gemini-3.8-flash"),
        )
        work_items.append(creator_input)

    return {"work_items": work_items, "prompt_version": PROMPT_VERSION}
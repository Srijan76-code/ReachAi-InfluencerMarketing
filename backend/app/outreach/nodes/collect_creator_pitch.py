from app.outreach.state import OutreachState
from app.outreach.utils import current_creator_input


async def collect_creator_pitch(state: OutreachState) -> OutreachState:
    creator_input = current_creator_input(state)
    creator_id = creator_input.get("creator_id", "")
    validation = (state.get("creator_validations") or {}).get(creator_id, {})
    repair_count = (state.get("creator_repair_counts") or {}).get(creator_id, 0)
    status = "completed" if validation.get("passed") else "needs_review"
    return {
        "pitch_results": [{
            "creator_id": creator_id,
            "selection_index": creator_input.get("selection_index", 0),
            "status": status,
            "pitch_bundle": (state.get("creator_pitch_bundles") or {}).get(creator_id, {}),
            "validation_errors": validation.get("errors") or [],
            "repair_count": repair_count,
        }]
    }
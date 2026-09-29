from app.outreach.state import OutreachState


async def collect_creator_pitch(state: OutreachState) -> OutreachState:
    creator_input = state.get("creator_input") or {}
    status = "completed" if state.get("validation_passed") else "needs_review"
    return {
        "pitch_results": [{
            "creator_id": creator_input.get("creator_id", ""),
            "selection_index": creator_input.get("selection_index", 0),
            "status": status,
            "pitch_bundle": state.get("pitch_bundle") or {},
            "validation_errors": state.get("validation_errors") or [],
            "repair_count": state.get("repair_count") or 0,
        }]
    }
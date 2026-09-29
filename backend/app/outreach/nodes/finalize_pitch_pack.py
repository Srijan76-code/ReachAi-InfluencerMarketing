from app.outreach.state import OutreachState


async def finalize_pitch_pack(state: OutreachState) -> OutreachState:
    results = sorted(state.get("pitch_results") or [], key=lambda item: item.get("selection_index", 0))
    completed = [item for item in results if item.get("status") == "completed"]
    needs_review = [item for item in results if item.get("status") != "completed"]
    reachable_channels = sum(
        sum(1 for field in ("email", "instagram", "twitter", "linkedin") if (item.get("pitch_bundle") or {}).get(field))
        for item in results
    )
    pitch_pack = {
        "outreach_job_id": state.get("outreach_job_id"),
        "campaign_id": state.get("campaign_id"),
        "creators": results,
    }
    return {
        "pitch_pack": pitch_pack,
        "generation_stats": {
            "creator_count": len(results),
            "successful_count": len(completed),
            "needs_review_count": len(needs_review),
            "reachable_channel_count": reachable_channels,
            "repair_count": sum(item.get("repair_count", 0) for item in results),
        },
    }
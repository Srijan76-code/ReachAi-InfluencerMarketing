from app.outreach.nodes.validate_creator_pitch import validate_bundle


CREATOR_INPUT = {
    "creator_id": "saumya",
    "available_channels": ["email"],
    "campaign_context": {"brand": {"name": "DataLaunch"}},
    "creator_identity": {"name": "Saumya Singh"},
    "collaboration": {"type": "sponsored_video"},
    "deliverables": ["1x 60s Mid-roll Integration", "Pinned Comment & Top Description Link"],
    "evidence": [{"evidence_id": "video_1"}],
}


def _bundle(body: str) -> dict:
    return {
        "creator_id": "saumya",
        "pitch_angle": "A thoughtful fit for DataLaunch and Saumya Singh's early-career audience.",
        "personalization": [{"evidence_id": "video_1", "reason": "Her career guidance is practical."}],
        "email": {"subject": "A quick idea for DataLaunch", "body": body},
    }


def test_accepts_a_natural_pitch_without_package_language():
    errors = validate_bundle(
        _bundle(
            "Hi Saumya Singh,\n\nYour practical career guidance stood out to us. "
            "DataLaunch helps early-career developers build job-ready data skills.\n\n"
            "Would you be open to exploring a collaboration?"
        ),
        CREATOR_INPUT,
    )

    assert errors == []


def test_rejects_raw_package_language_and_formulaic_openers():
    errors = validate_bundle(
        _bundle(
            "Hi Saumya Singh,\n\nI loved your guide in 'Your PERFECT Tech Career in 2026'. "
            "DataLaunch would love a sponsored_video featuring a 1x 60s Mid-roll Integration, "
            "Pinned Comment & Top Description Link.\n\nWould you be open to a collaboration?"
        ),
        CREATOR_INPUT,
    )

    assert any("raw snake_case" in error for error in errors)
    assert any("package detail" in error for error in errors)
    assert any("formulaic opener" in error for error in errors)

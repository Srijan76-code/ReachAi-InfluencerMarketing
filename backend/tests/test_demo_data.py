"""The public /demo page ships data with the frontend. Guard it:
- no email addresses are published,
- every sample pitch passes the same validator real pitches go through,
- pitches only reference creators that exist in the demo leads.
"""

import json
import re
from pathlib import Path

import pytest

from app.outreach.nodes.validate_creator_pitch import validate_bundle
from app.outreach.utils import available_channels

DEMO = Path(__file__).resolve().parents[2] / "frontend" / "data" / "demo"
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

LEADS = json.loads((DEMO / "leads.json").read_text())
PITCHES = json.loads((DEMO / "pitches.json").read_text())
LEADS_BY_ID = {lead["id"]: lead for lead in LEADS}


def test_no_email_addresses_in_public_demo_data():
    for name in ("leads.json", "pitches.json"):
        found = EMAIL.findall((DEMO / name).read_text())
        assert not found, f"{name} publishes email addresses: {found}"


def test_leads_have_what_the_results_ui_needs():
    assert len(LEADS) >= 5
    for lead in LEADS:
        for key in ("id", "title", "subscribers", "metrics", "final_score", "deal_status", "valuation", "llm_reasoning"):
            assert lead.get(key) not in (None, ""), (lead.get("title"), key)
        assert lead["deal_status"] in {"Strong Buy", "Consider", "Avoid"}


def test_pitches_reference_real_demo_creators():
    assert PITCHES
    for pitch in PITCHES:
        assert pitch["creatorId"] in LEADS_BY_ID


def _bundle(pitch):
    bundle = {
        "creator_id": pitch["creatorId"],
        "pitch_angle": pitch["pitchAngle"],
        "personalization": [{"evidence_id": "video_1", "reason": "References a recent video."}],
        "email": pitch.get("email"),
        "instagram": {"body": pitch["instagram"]} if pitch.get("instagram") else None,
        "twitter": {"body": pitch["twitter"]} if pitch.get("twitter") else None,
        "linkedin": None,
    }
    return bundle


@pytest.mark.parametrize("pitch", PITCHES, ids=[p["creatorId"] for p in PITCHES])
def test_sample_pitch_passes_the_real_validator(pitch):
    lead = LEADS_BY_ID[pitch["creatorId"]]
    bundle = _bundle(pitch)
    channels = [c for c in ("email", "instagram", "twitter", "linkedin") if bundle.get(c)]
    creator_input = {
        "creator_id": pitch["creatorId"],
        "available_channels": channels,
        "evidence": [{"evidence_id": "video_1"}],
        "campaign_context": {"brand": {"name": "DataLaunch"}},
        "creator_identity": {"name": ""},  # demo pitches greet by first name, not channel title
        "collaboration": {"type": "sponsored_video"},
    }
    errors = validate_bundle(bundle, creator_input)
    assert errors == [], (lead["title"], errors)


def test_pitch_channels_are_ones_the_creator_was_reachable_on():
    from data.influencer_list import final_ranked_leads  # original data, emails included

    original = {lead["id"]: lead for lead in final_ranked_leads}
    for pitch in PITCHES:
        reachable = set(available_channels(original[pitch["creatorId"]]))
        used = {c for c in ("email", "instagram", "twitter") if pitch.get(c)}
        assert used <= reachable, (pitch["creatorId"], used - reachable)

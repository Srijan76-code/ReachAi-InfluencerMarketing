from tests.evals.dataset import build_evaluation_cases
from tests.evals.evaluators import evaluate_case


def test_missing_evidence_reference_fails():
    case = build_evaluation_cases()[0]
    output = {"pitch_bundle": {"creator_id": case["expected"]["creator_id"], "pitch_angle": "x", "personalization": [{"evidence_id": "not-real", "reason": "x"}], "instagram": {"body": "x"}}}
    results = {result["key"]: result for result in evaluate_case(case, output)}
    assert results["evidence_ids_valid"]["score"] == 0.0


def test_empty_available_channel_fails():
    case = build_evaluation_cases()[0]
    output = {"pitch_bundle": {"creator_id": case["expected"]["creator_id"], "pitch_angle": "x", "personalization": [], "instagram": {"body": ""}}}
    results = {result["key"]: result for result in evaluate_case(case, output)}
    assert results["available_channels_nonempty"]["score"] == 0.0

from tests.evals.dataset import build_evaluation_cases
from tests.evals.evaluators import evaluate_case


def _valid_output(case):
    expected = case["expected"]
    channels = expected["available_channels"]
    bundle = {
        "creator_id": expected["creator_id"],
        "pitch_angle": "A practical campaign angle grounded in recent creator work.",
        "personalization": [{"evidence_id": expected["allowed_evidence_ids"][0], "reason": "Recent relevant creator evidence."}],
    }
    for channel in channels:
        if channel == "email":
            bundle[channel] = {"subject": "A practical collaboration", "body": _body(case)}
        else:
            bundle[channel] = {"body": _body(case)}
    return {"pitch_bundle": bundle}


def _body(case):
    # A realistic valid first message: names the creator and brand, invites a collaboration,
    # and keeps package details (deliverables, placements) out of the copy.
    expected = case["expected"]
    return (
        f"Hi {expected['creator_name']}, your recent breakdowns really resonated with our team. "
        f"{expected['brand_name']} helps your audience with exactly that problem, and we'd love to explore "
        "a collaboration with you. Would you be open to a quick chat?"
    )


def test_deterministic_evaluators_accept_valid_bundle():
    case = build_evaluation_cases()[0]
    results = evaluate_case(case, _valid_output(case))
    assert all(result["score"] == 1.0 for result in results)


def test_deterministic_evaluators_reject_unavailable_channel_and_internal_data():
    case = build_evaluation_cases()[0]
    output = _valid_output(case)
    output["pitch_bundle"]["email"] = {"subject": "x", "body": "final_score 93"}
    results = {result["key"]: result for result in evaluate_case(case, output)}
    assert results["channel_set_correct"]["score"] == 0.0
    assert results["forbidden_internal_data_absent"]["score"] == 0.0


def test_valid_bundle_passes_for_every_case():
    for case in build_evaluation_cases():
        failed = [r["key"] for r in evaluate_case(case, _valid_output(case)) if r["score"] != 1.0]
        assert not failed, (case["expected"]["creator_name"], failed)


def test_missing_collaboration_invitation_is_flagged():
    case = build_evaluation_cases()[0]
    output = _valid_output(case)
    for channel, value in output["pitch_bundle"].items():
        if isinstance(value, dict) and "body" in value:
            value["body"] = value["body"].replace("a collaboration", "something")
    results = {result["key"]: result for result in evaluate_case(case, output)}
    assert results["collaboration_correct"]["score"] == 0.0


def test_package_details_are_flagged():
    case = build_evaluation_cases()[0]
    output = _valid_output(case)
    first = next(k for k, v in output["pitch_bundle"].items() if isinstance(v, dict) and "body" in v)
    output["pitch_bundle"][first]["body"] += " Includes a pinned comment."
    results = {result["key"]: result for result in evaluate_case(case, output)}
    assert results["package_details_absent"]["score"] == 0.0


def test_too_many_questions_are_flagged():
    case = build_evaluation_cases()[0]
    output = _valid_output(case)
    first = next(k for k, v in output["pitch_bundle"].items() if isinstance(v, dict) and "body" in v)
    output["pitch_bundle"][first]["body"] += " Free? Now? Soon? Really?"
    results = {result["key"]: result for result in evaluate_case(case, output)}
    assert results["question_count_valid"]["score"] == 0.0

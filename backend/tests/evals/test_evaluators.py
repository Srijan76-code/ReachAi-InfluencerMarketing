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
    expected = case["expected"]
    facts = expected["required_facts"]
    return f"{expected['creator_name']}, {expected['brand_name']} proposes {facts['collaboration_type']} for {', '.join(facts['deliverables'])}. Interested?"


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

from tests.evals.dataset import build_evaluation_cases
from tests.evals.evaluators import batch_isolation_results


def test_batch_results_keep_creator_identity_and_selection_order():
    cases = build_evaluation_cases()[:3]
    outputs = [
        {"pitch_bundle": {"creator_id": case["expected"]["creator_id"], "pitch_angle": case["expected"]["creator_name"]}}
        for case in cases
    ]
    results = batch_isolation_results(outputs, cases)
    assert all(result["score"] == 1.0 for result in results)


def test_batch_isolation_detects_cross_creator_output():
    all_cases = build_evaluation_cases()
    cases = [all_cases[0], all_cases[4]]
    outputs = [{"pitch_bundle": {"creator_id": cases[0]["expected"]["creator_id"], "pitch_angle": cases[1]["expected"]["creator_name"]}}, {"pitch_bundle": {"creator_id": cases[1]["expected"]["creator_id"], "pitch_angle": cases[1]["expected"]["creator_name"]}}]
    results = batch_isolation_results(outputs, cases)
    assert results[0]["score"] == 1.0
    assert results[1]["score"] == 0.0
    assert results[2]["score"] == 1.0
    assert results[3]["score"] == 1.0

from tests.evals.dataset import build_evaluation_cases


def test_dataset_uses_real_leads_and_has_balanced_variants():
    cases = build_evaluation_cases()
    assert len(cases) == 28
    assert len({case["expected"]["creator_id"] for case in cases}) == 7
    assert len({case["expected"]["required_facts"]["collaboration_type"] for case in cases}) == 4
    assert any(case["expected"]["available_channels"] == ["instagram"] for case in cases)
    assert any("email" in case["expected"]["available_channels"] for case in cases)
    assert any("twitter" in case["expected"]["available_channels"] for case in cases)


def test_dataset_does_not_expose_internal_scores_as_expected_facts():
    for case in build_evaluation_cases():
        forbidden = case["expected"]["forbidden_internal_data"]
        assert all(term not in case["expected"]["required_facts"] for term in forbidden)

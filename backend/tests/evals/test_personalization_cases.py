from tests.evals.dataset import build_evaluation_cases


def test_same_campaign_different_creators_are_explicit_cases():
    cases = build_evaluation_cases()
    paid = [case for case in cases if case["id"].endswith("::paid_instagram")]
    assert len(paid) == 7
    assert len({case["inputs"]["creator"]["id"] for case in paid}) == 7
    assert len({case["inputs"]["creator"].get("llm_reasoning") for case in paid}) > 1


def test_same_creator_has_collaboration_and_campaign_variants():
    cases = build_evaluation_cases()
    creator_id = cases[0]["expected"]["creator_id"]
    creator_cases = [case for case in cases if case["expected"]["creator_id"] == creator_id]
    assert len(creator_cases) == 4
    assert len({case["expected"]["required_facts"]["collaboration_type"] for case in creator_cases}) == 4
    assert len({case["inputs"]["campaign_context"]["campaign"]["goal"] for case in creator_cases}) == 2

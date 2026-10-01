import re
from typing import Any, Dict, Iterable, List

from app.schemas.outreach import PitchBundle

CHANNELS = ("email", "instagram", "twitter", "linkedin")


def _bundle(output: Dict[str, Any]) -> Dict[str, Any]:
    if "pitch_bundle" in output:
        return output["pitch_bundle"] or {}
    creators = ((output.get("pitch_pack") or {}).get("creators") or [])
    return (creators[0].get("pitch_bundle") if creators else None) or {}


def _text(bundle: Dict[str, Any]) -> str:
    values = [str(bundle.get("pitch_angle", ""))]
    for item in bundle.get("personalization") or []:
        values.extend([str(item.get("evidence_id", "")), str(item.get("reason", ""))])
    for channel in CHANNELS:
        value = bundle.get(channel)
        if value:
            values.extend(str(part) for part in value.values())
    return "\n".join(values)


def _result(key: str, passed: bool, reason: str) -> Dict[str, Any]:
    return {"key": key, "score": 1.0 if passed else 0.0, "value": passed, "comment": reason}


def evaluate_case(case: Dict[str, Any], output: Dict[str, Any]) -> List[Dict[str, Any]]:
    expected = case["expected"]
    bundle = _bundle(output)
    text = _text(bundle)
    lowered = text.lower()
    results: List[Dict[str, Any]] = []
    try:
        PitchBundle.model_validate(bundle)
        results.append(_result("schema_valid", True, "PitchBundle matches the output schema."))
    except Exception as exc:
        results.append(_result("schema_valid", False, f"Invalid PitchBundle: {exc}"))

    results.append(_result("creator_id_correct", bundle.get("creator_id") == expected["creator_id"], "Creator ID matches the case."))
    results.append(_result("creator_name_correct", expected["creator_name"].lower() in lowered, "Creator name is present."))
    results.append(_result("brand_name_correct", expected["brand_name"].lower() in lowered, "Brand name is present."))
    collaboration = expected["required_facts"]["collaboration_type"].lower()
    results.append(_result("collaboration_correct", collaboration in lowered, "Collaboration type is represented."))
    missing_deliverables = [item for item in expected["required_facts"]["deliverables"] if item.lower() not in lowered]
    results.append(_result("deliverables_correct", not missing_deliverables, "All deliverables are represented." if not missing_deliverables else f"Missing deliverables: {missing_deliverables}"))

    actual_channels = sorted(channel for channel in CHANNELS if bundle.get(channel) is not None)
    expected_channels = sorted(expected["available_channels"])
    results.append(_result("channel_set_correct", actual_channels == expected_channels, f"Expected {expected_channels}, got {actual_channels}."))

    evidence_ids = {item.get("evidence_id") for item in bundle.get("personalization") or []}
    allowed = set(expected["allowed_evidence_ids"])
    invalid_evidence = sorted(evidence_ids - allowed)
    results.append(_result("evidence_ids_valid", not invalid_evidence, "Evidence references are valid." if not invalid_evidence else f"Invalid evidence IDs: {invalid_evidence}"))

    question_count = text.count("?")
    results.append(_result("question_count_valid", question_count <= expected["max_questions"], f"Question count: {question_count}."))
    forbidden = [term for term in expected["forbidden_internal_data"] if re.search(rf"\b{re.escape(term.lower())}\b", lowered)]
    results.append(_result("forbidden_internal_data_absent", not forbidden, "No internal scoring data exposed." if not forbidden else f"Forbidden terms found: {forbidden}"))

    empty_available = [channel for channel in expected_channels if not _channel_has_text(bundle.get(channel))]
    results.append(_result("available_channels_nonempty", not empty_available, "Available channel pitches are non-empty." if not empty_available else f"Empty channels: {empty_available}"))
    return results


def _channel_has_text(value: Any) -> bool:
    return bool(value and any(str(part).strip() for part in value.values()))


def aggregate_code_score(results: Iterable[Dict[str, Any]]) -> float:
    values = [float(result["score"]) for result in results]
    return sum(values) / len(values) if values else 0.0


def code_evaluator(run: Any, example: Any) -> List[Dict[str, Any]]:
    case = {"inputs": example.inputs, "expected": example.outputs or {}}
    return evaluate_case(case, run.outputs or {})


def batch_isolation_results(outputs: List[Dict[str, Any]], cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    creator_names = {case["expected"]["creator_name"].lower() for case in cases}
    for case, output in zip(cases, outputs):
        bundle = _bundle(output)
        results.append(_result("creator_id_isolated", bundle.get("creator_id") == case["expected"]["creator_id"], "Creator ID matches the case."))
        text = _text(bundle).lower()
        other_names = creator_names - {case["expected"]["creator_name"].lower()}
        results.append(_result("creator_content_isolated", not any(name in text for name in other_names), "No other case creator name appears in this pitch."))
    return results

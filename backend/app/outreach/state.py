from typing import Annotated, Any, Dict, List, Optional, TypedDict
from operator import add


def merge_creator_maps(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    return {**(left or {}), **(right or {})}


class CreatorPitchInput(TypedDict, total=False):
    creator_id: str
    selection_index: int
    campaign_context: Dict[str, Any]
    collaboration: Dict[str, Any]
    deliverables: List[str]
    creator_identity: Dict[str, Any]
    creator_description: str
    rich_context: str
    recent_videos: List[Dict[str, Any]]
    fit_reasoning: str
    relevance_score: float
    available_channels: List[str]
    social_links: Dict[str, Optional[str]]
    evidence: List[Dict[str, Any]]


class CreatorPitchResult(TypedDict, total=False):
    creator_id: str
    selection_index: int
    status: str
    pitch_bundle: Dict[str, Any]
    validation_errors: List[str]
    repair_count: int


class OutreachState(TypedDict, total=False):
    outreach_job_id: str
    campaign_id: str
    campaign_context: Dict[str, Any]
    selected_creators: List[Dict[str, Any]]
    default_collaboration: Dict[str, Any]
    default_deliverables: List[str]
    creator_overrides: Dict[str, Dict[str, Any]]
    model_name: str
    work_items: List[CreatorPitchInput]
    creator_input: CreatorPitchInput
    creator_inputs: Annotated[Dict[str, CreatorPitchInput], merge_creator_maps]
    pitch_bundle: Dict[str, Any]
    creator_pitch_bundles: Annotated[Dict[str, Dict[str, Any]], merge_creator_maps]
    validation_errors: List[str]
    creator_validations: Annotated[Dict[str, Dict[str, Any]], merge_creator_maps]
    repair_count: int
    creator_repair_counts: Annotated[Dict[str, int], merge_creator_maps]
    validation_passed: bool
    prompt_version: str
    cache_key: str
    pitch_results: Annotated[List[CreatorPitchResult], add]
    pitch_pack: Dict[str, Any]
    generation_stats: Dict[str, Any]
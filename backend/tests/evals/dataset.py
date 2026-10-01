from copy import deepcopy
from typing import Any, Dict, List

from data.influencer_list import final_ranked_leads


DATASET_NAME = "reach-ai-outreach-real-leads-v1"

BASE_CAMPAIGN_CONTEXT = {
    "brand": {
        "name": "DataLaunch",
        "industry": "edtech",
        "business_model": "education",
        "product_price_range": "high ticket",
        "core_outcome": "advanced AI and machine learning courses",
    },
    "audience": {
        "target_persona": "junior developers and fresh CS graduates building AI/ML careers",
        "locations": ["India"],
        "languages": ["English", "Hindi"],
    },
    "campaign": {
        "goal": "reach serious learners and drive qualified course enrollments",
        "creator_authority_level": "technical educator",
        "platform": "YouTube",
        "budget_total": 10000,
        "creator_count": 1,
    },
    "content_topics": ["machine learning", "generative AI", "coding careers", "practical projects"],
    "video_formats": ["tutorial", "roadmap", "case study"],
    "pain_points": ["choosing a practical AI learning path", "building job-ready projects"],
    "primary_metric": "creator_authority",
    "safety_level": "high",
}

ALTERNATE_CAMPAIGN_CONTEXT = deepcopy(BASE_CAMPAIGN_CONTEXT)
ALTERNATE_CAMPAIGN_CONTEXT["campaign"] = {
    **BASE_CAMPAIGN_CONTEXT["campaign"],
    "goal": "build awareness for a practical AI project-learning cohort",
}
ALTERNATE_CAMPAIGN_CONTEXT["pain_points"] = [
    "turning tutorials into portfolio projects",
    "finding credible practical guidance",
]

VARIANTS = [
    {
        "name": "paid_instagram",
        "collaboration": "paid sponsorship",
        "deliverables": ["one Instagram post"],
        "campaign": BASE_CAMPAIGN_CONTEXT,
    },
    {
        "name": "affiliate_story",
        "collaboration": "affiliate",
        "deliverables": ["one Instagram story"],
        "campaign": BASE_CAMPAIGN_CONTEXT,
    },
    {
        "name": "gifting_multi_deliverable",
        "collaboration": "gifting",
        "deliverables": ["one Instagram post", "one YouTube integration"],
        "campaign": BASE_CAMPAIGN_CONTEXT,
    },
    {
        "name": "partnership_alternate_campaign",
        "collaboration": "long-term partnership",
        "deliverables": ["one Instagram post"],
        "campaign": ALTERNATE_CAMPAIGN_CONTEXT,
    },
]


def _creator_evidence_ids(creator: Dict[str, Any]) -> List[str]:
    video_ids = [f"video_{index}" for index, _ in enumerate(creator.get("recent_videos") or [], start=1)]
    return video_ids + (["creator_reasoning"] if creator.get("llm_reasoning") else [])


def _case_creator(creator: Dict[str, Any]) -> Dict[str, Any]:
    # Keep the real lead snapshot intact for the real graph; evaluators only expose
    # the compact prepared fields and never score internal ranking fields.
    return deepcopy(creator)


def build_evaluation_cases() -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    for creator in final_ranked_leads:
        channels = [name for name, value in (creator.get("socials") or {}).items() if value]
        for variant in VARIANTS:
            case_id = f"{creator['id']}::{variant['name']}"
            cases.append(
                {
                    "id": case_id,
                    "inputs": {
                        "campaign_context": deepcopy(variant["campaign"]),
                        "creator": _case_creator(creator),
                        "collaboration": {"type": variant["collaboration"]},
                        "deliverables": list(variant["deliverables"]),
                        "available_channels": channels,
                        "creator_overrides": {
                            creator["id"]: {
                                "collaboration_type": variant["collaboration"],
                                "deliverables": list(variant["deliverables"]),
                            }
                        },
                    },
                    "expected": {
                        "creator_id": creator["id"],
                        "creator_name": creator["title"],
                        "brand_name": variant["campaign"]["brand"]["name"],
                        "available_channels": channels,
                        "allowed_evidence_ids": _creator_evidence_ids(creator),
                        "required_facts": {
                            "collaboration_type": variant["collaboration"],
                            "deliverables": list(variant["deliverables"]),
                        },
                        "forbidden_internal_data": [
                            "final_score",
                            "valuation",
                            "health_score",
                            "trust_score",
                            "semantic_score",
                            "risk_penalty",
                            "deal_status",
                        ],
                        "max_questions": 2,
                    },
                }
            )
    return cases


def seed_langsmith_dataset(client: Any, dataset_name: str = DATASET_NAME) -> Any:
    cases = build_evaluation_cases()
    if client.has_dataset(dataset_name=dataset_name):
        return next(client.list_datasets(dataset_name=dataset_name, limit=1))
    dataset = client.create_dataset(
        dataset_name,
        description="Real Reach AI ranked creator leads evaluated through the outreach graph.",
        inputs_schema={"type": "object"},
        outputs_schema={"type": "object"},
        metadata={"source": "backend/data/influencer_list.py", "case_count": len(cases)},
    )
    client.create_examples(
        dataset_id=dataset.id,
        examples=[{"inputs": case["inputs"], "outputs": case["expected"], "metadata": {"case_id": case["id"]}} for case in cases],
    )
    return dataset

import asyncio
import json
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from app.core.model import model


class OutreachJudgeScore(BaseModel):
    groundedness: float = Field(ge=0, le=1)
    personalization: float = Field(ge=0, le=1)
    campaign_relevance: float = Field(ge=0, le=1)
    naturalness: float = Field(ge=0, le=1)
    channel_fit: float = Field(ge=0, le=1)
    value_proposition: float = Field(ge=0, le=1)
    cta_quality: float = Field(ge=0, le=1)
    creator_specificity: float = Field(ge=0, le=1)
    issues: List[str] = Field(default_factory=list)
    overall_reason: str


JUDGE_WEIGHTS = {
    "groundedness": 0.25,
    "personalization": 0.25,
    "campaign_relevance": 0.20,
    "naturalness": 0.10,
    "creator_specificity": 0.10,
    "channel_fit": 0.05,
    "cta_quality": 0.05,
}


def _judge_prompt(case: Dict[str, Any], output: Dict[str, Any]) -> str:
    return f"""
Evaluate one creator outreach pitch pack. Return scores from 0 to 1 using the supplied
campaign, creator evidence, collaboration, deliverables, available channels, and pitch only.
Do not infer facts that are not present in the inputs.

Groundedness: creator-specific claims are supported by supplied evidence.
Personalization: this pitch could not be sent unchanged to another creator.
Campaign relevance: the pitch connects to the supplied brand and goal.
Naturalness: human, credible, not inflated or formulaic.
Channel fit: each available channel is adapted appropriately.
Value proposition: the creator has a concrete reason to care.
CTA quality: clear and low friction.
Creator specificity: low if generic compliments could replace the creator.

CASE:
{json.dumps(case, default=str)}

GENERATED OUTPUT:
{json.dumps(output, default=str)}
""".strip()


async def judge_pitch(case: Dict[str, Any], output: Dict[str, Any]) -> OutreachJudgeScore:
    structured_model = model.with_structured_output(OutreachJudgeScore)
    result = await asyncio.to_thread(structured_model.invoke, _judge_prompt(case, output))
    return result if isinstance(result, OutreachJudgeScore) else OutreachJudgeScore.model_validate(result)


def aggregate_judge_score(score: OutreachJudgeScore) -> float:
    return sum(getattr(score, key) * weight for key, weight in JUDGE_WEIGHTS.items())


def judge_evaluator(run: Any, example: Any) -> List[Dict[str, Any]]:
    case = {"inputs": example.inputs, "expected": example.outputs or {}}
    score = asyncio.run(judge_pitch(case, run.outputs or {}))
    values = score.model_dump()
    results = [
        {"key": key, "score": values[key], "comment": score.overall_reason}
        for key in JUDGE_WEIGHTS
    ]
    results.append({"key": "overall_quality", "score": aggregate_judge_score(score), "comment": score.overall_reason})
    results.append({"key": "judge_issues", "value": score.issues, "comment": score.overall_reason})
    return results

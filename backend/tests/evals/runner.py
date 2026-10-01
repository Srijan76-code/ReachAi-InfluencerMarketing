import argparse
import asyncio
import json
from typing import Any, Dict

from langgraph.cache.memory import InMemoryCache
from langgraph.checkpoint.memory import InMemorySaver
from langsmith import Client

from app.outreach.graph import build_outreach_graph
from tests.evals.dataset import DATASET_NAME, build_evaluation_cases, seed_langsmith_dataset
from tests.evals.evaluators import code_evaluator
from tests.evals.judge import judge_evaluator


def _initial_state(inputs: Dict[str, Any]) -> Dict[str, Any]:
    creator = inputs["creator"]
    creator_id = creator["id"]
    return {
        "outreach_job_id": f"eval-{creator_id}",
        "campaign_id": "evaluation-campaign",
        "campaign_context": inputs["campaign_context"],
        "selected_creators": [creator],
        "default_collaboration": inputs["collaboration"],
        "default_deliverables": inputs["deliverables"],
        "creator_overrides": inputs.get("creator_overrides", {}),
        "model_name": "gemini-3.8-flash",
    }


def run_graph_case(inputs: Dict[str, Any]) -> Dict[str, Any]:
    async def invoke() -> Dict[str, Any]:
        workflow = build_outreach_graph().compile(
            checkpointer=InMemorySaver(),
            cache=InMemoryCache(),
        )
        config = {
            "configurable": {"thread_id": f"eval-{inputs['creator']['id']}"},
            "max_concurrency": 5,
            "metadata": {"evaluation": True},
        }
        return await workflow.ainvoke(_initial_state(inputs), config=config)

    result = asyncio.run(invoke())
    return {
        "pitch_pack": result.get("pitch_pack", {}),
        "pitch_results": result.get("pitch_results", []),
        "generation_stats": result.get("generation_stats", {}),
    }


def run_langsmith(dataset_name: str = DATASET_NAME, experiment_prefix: str = "outreach") -> Any:
    client = Client()
    seed_langsmith_dataset(client, dataset_name)
    return client.evaluate(
        run_graph_case,
        data=dataset_name,
        evaluators=[code_evaluator, judge_evaluator],
        experiment_prefix=experiment_prefix,
        description="Reach AI outreach regression evaluation using real ranked leads.",
        max_concurrency=5,
        blocking=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-only", action="store_true")
    parser.add_argument("--dataset", default=DATASET_NAME)
    parser.add_argument("--experiment-prefix", default="outreach")
    args = parser.parse_args()
    client = Client()
    dataset = seed_langsmith_dataset(client, args.dataset)
    print(json.dumps({"dataset_id": str(dataset.id), "case_count": len(build_evaluation_cases())}, indent=2))
    if not args.seed_only:
        print(run_langsmith(args.dataset, args.experiment_prefix))


if __name__ == "__main__":
    main()

from pydantic import BaseModel, Field

import json
from math import ceil
from typing import List
import asyncio



from core.model import model
from utils.state import LLMState
MAX_CONCURRENT_LLM_CALLS = 5
BATCH_SIZE = 15


class CandidateGrade(BaseModel):
    id: str = Field(description="The EXACT candidate ID provided in input.")
    relevance_score: int = Field(
        description="0-100 Score. 100 = Perfect Brand/Audience Match."
    )
    reasoning: str = Field(
        description="Why does this fit the BRAND BRIEF? (Ignore metrics)."
    )


class BatchRelevanceGrade(BaseModel):
    results: List[CandidateGrade]


def Prompt_for_reranker(brand_brief_text, candidates_json):
    return f"""
    ROLE: You are a Senior Brand Strategist.
    TASK: Grade these channels purely on BRAND FIT and CONTENT RELEVANCE.
    
    IGNORE metrics (views, subs). Assume all are large enough.
    
    SCORING CRITERIA:
    - 0-30: Irrelevant Topic (e.g., Gaming vs FinTech).
    - 31-60: Weak Match (Right broad category, wrong audience).
    - 61-80: Strong Match (Good content fit).
    - 81-100: Perfect Match (Ideal niche & persona).

    BRAND BRIEF:
    {brand_brief_text}

    CANDIDATES:
    {candidates_json}
    
    OUTPUT:
    Return a valid JSON object with a 'results' list containing grades for ALL candidates.
    """


def chunk_list(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def normalize_candidate(cand):
    rc = cand.get("rich_context", {})

    c_name = cand.get("title", "Unknown")
    if c_name == "Unknown":
        c_name = rc.get("channel_name", "Unknown")

    videos = cand.get("recent_videos", [])
    if not videos:
        videos = rc.get("recent_videos", [])

    video_titles = []
    if videos and isinstance(videos[0], dict):
        video_titles = [v["title"] for v in videos[:8]]
    elif videos:
        video_titles = videos[:8]

    return {
        "id": cand["id"],
        "channel_name": c_name,
        "recent_videos": video_titles,
        "description": cand.get("description", "")[:400],
    }


async def run_batch(
    *, batch, batch_index, total_batches, structured_llm, brand_brief_text, semaphore
):
    print(
        f"   → Processing batch {batch_index}/{total_batches} ({len(batch)} channels)..."
    )

    candidates_json = json.dumps(batch, indent=2)

    prompt = Prompt_for_reranker(
        brand_brief_text=brand_brief_text, candidates_json=candidates_json
    )

    async with semaphore:
        try:
            batch_result = await asyncio.to_thread(structured_llm.invoke, prompt)

            received = batch_result.results
            batch_ids = {c["id"] for c in batch}
            valid = [g for g in received if g.id in batch_ids]

            dropped = len(batch) - len(valid)
            if dropped > 0:
                print(
                    f"     [WARN] Dropped {dropped} candidates (LLM skip/hallucination)."
                )

            return valid

        except Exception as e:
            print(f"     [!] Batch {batch_index} CRITICAL FAIL: {e}")
            return []


async def reranker_node(state: LLMState):
    print("\n--- 5. LLM RERANKER (Strategy Judge) ---")

    candidates = state.get("analyzed_leads", [])
    ctx = state.get("campaign_context", {})

    print(f"   > Received {len(candidates)} candidates from Semantic Processor.")
    if not candidates:
        return {"re_ranked_leads": []}

    brand_brief_text = f"""
    Brand Name: {ctx.get('name', 'Unknown')}
    Industry: {ctx.get('industry', 'General')}
    Product Price: {ctx.get('product_price_range', 'Unknown')}
    Target Audience: {ctx.get('target_persona', 'General Audience')}
    Campaign Goal: {ctx.get('goal', 'Brand Awareness')}
    Key Pain Points: {", ".join(ctx.get('pain_points', []))}
    """.strip()

    normalized_candidates = [normalize_candidate(c) for c in candidates]

    structured_llm = model.with_structured_output(BatchRelevanceGrade)

    batches = list(chunk_list(normalized_candidates, BATCH_SIZE))
    total_batches = len(batches)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM_CALLS)

    tasks = [
        asyncio.create_task(
            run_batch(
                batch=batch,
                batch_index=i + 1,
                total_batches=total_batches,
                structured_llm=structured_llm,
                brand_brief_text=brand_brief_text,
                semaphore=semaphore,
            )
        )
        for i, batch in enumerate(batches)
    ]

    all_results = []
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for batch_res in results:
        if isinstance(batch_res, list):
            all_results.extend(batch_res)

    result_map = {r.id: r for r in all_results}

    ranked_leads = []
    for cand in candidates:
        grade = result_map.get(cand["id"])
        if not grade:
            continue

        if grade.relevance_score >= 50:
            cand["relevance_score"] = grade.relevance_score
            cand["llm_reasoning"] = grade.reasoning
            ranked_leads.append(cand)

    ranked_leads.sort(key=lambda x: x["relevance_score"], reverse=True)

    print(f"   > Final Ranked Leads: {len(ranked_leads)}")
    return {"re_ranked_leads": ranked_leads}

from pydantic import BaseModel, Field

import json
from math import ceil
from typing import List
import asyncio


from core.model import model
from ..utils.state import LLMState

MAX_CONCURRENT_LLM_CALLS = 5
BATCH_SIZE = 15

class CandidateReasoning(BaseModel):
    id: str = Field(description="Exact candidate ID from input.")
    reasoning: str = Field(
        description="One sentence explaining why this audience will or will not convert for the brand."
    )


class BatchCandidateReasoning(BaseModel):
    results: List[CandidateReasoning] = Field(
        description="Reasoning for ALL input candidates."
    )

def reasoning_prompt(selected, reasoning_brief_text):
    return f"""
    ROLE: Conversion Strategist.

    TASK:
    Explain clearly why this influencer’s audience will or will not convert for this brand.

    STYLE:
    - One sentence only (15–22 words)
    - Natural, human, readable
    - Direct and decisive

    FOCUS ON:
    - Audience intent
    - Audience stage vs product level
    - Alignment with brand’s outcome

    IMPORTANT:
    - Must reference the brand/product
    - Must explain conversion likelihood naturally
    - Do NOT mention metrics
    - Do NOT describe content

    ---

    GOOD EXAMPLES:

    "His audience is actively learning ML and aligns well with DataLaunch’s advanced courses, making conversions highly likely."

    "Her audience is mostly beginners exploring tech, so they are less likely to convert for DataLaunch’s advanced offering."

    "This audience is career-focused but not specifically on AI, reducing direct relevance to DataLaunch’s core product."

    "Viewers show interest in AI but lack strong purchase intent, making conversions possible but inconsistent for DataLaunch."

    ---

    BRAND CONTEXT:
    {reasoning_brief_text}

    INFLUENCER:
    {selected}

    ---

    OUTPUT:
    Return reasoning only.
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


async def run_reasoning_batch(
    *, batch, batch_index, total_batches, structured_llm, reasoning_brief_text, semaphore
):
    print(
        f"   → Processing reasoning batch {batch_index}/{total_batches} ({len(batch)} creators)..."
    )

    async with semaphore:
        try:
            results = []

            # reasoning is per influencer (not bulk JSON like scoring)
            for c in batch:
                prompt = reasoning_prompt(c, reasoning_brief_text)

                res = await asyncio.to_thread(structured_llm.invoke, prompt)

                results.append(res)

            return results

        except Exception as e:
            print(f"     [!] Reasoning batch {batch_index} FAILED: {e}")
            return []

async def llm_reasoning_node(state: LLMState):
    print("\n--- 6. LLM REASONING (Conversion Layer) ---")

    final_leads = state.get("final_ranked_leads", [])
    ctx = state.get("campaign_context", {})
    campaign = state.get("campaign", {})

    if not final_leads:
        return {"final_ranked_leads": []}

    # 👉 only top N creators (pricing logic)
    creator_count = campaign.get("creator_count", 5)
    selected = final_leads[:creator_count]

    print(f"   > Generating reasoning for top {len(selected)} creators")

    # ---- Build reasoning context (clean narrative) ----
    brand = ctx.get("brand", {})
    audience = ctx.get("audience", {})
    campaign_ctx = ctx.get("campaign", {})

    reasoning_brief_text = f"""
    Brand {brand.get('name', 'Unknown')} offers {brand.get('core_outcome', 'a product')}.

    It is designed for {audience.get('target_persona', 'general users')}.

    The goal is to {campaign_ctx.get('goal', 'drive outcomes')} by solving:
    {", ".join(ctx.get('pain_points', []))}
    """.strip()

    # ---- Normalize candidates (reuse same function) ----
    normalized = [normalize_candidate(c) for c in selected]

    structured_llm = model.with_structured_output(CandidateReasoning)

    batches = list(chunk_list(normalized, BATCH_SIZE))
    total_batches = len(batches)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM_CALLS)

    tasks = [
        asyncio.create_task(
            run_reasoning_batch(
                batch=batch,
                batch_index=i + 1,
                total_batches=total_batches,
                structured_llm=structured_llm,
                reasoning_brief_text=reasoning_brief_text,
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

    # ---- Map results ----
    result_map = {r.id: r for r in all_results}

    for c in final_leads:
        if c["id"] in result_map:
            c["llm_reasoning"] = result_map[c["id"]].reasoning

    print(f"   > Reasoning generated for {len(result_map)} creators")

    return {"final_ranked_leads": final_leads}
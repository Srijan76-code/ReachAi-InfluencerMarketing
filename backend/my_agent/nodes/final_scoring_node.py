
from utils.state import LLMState


def final_scoring_node(state: LLMState):
    print("\n--- 5. FINAL SCORING (Fusion) ---")

    candidates = state.get("re_ranked_leads", [])
    if not candidates:
        return {"final_ranked_leads": []}

    scored_leads = []

    risk_factor = {"High": 1.0, "Medium": 0.85, "Low": 0.70}

    for c in candidates:
        metrics = c.get("metrics", {})

        llm_score = c.get("relevance_score", 0)
        trust_score = metrics.get("trust_score", 0)
        reliability = metrics.get("reliability", "Medium")

        health_score = trust_score * risk_factor.get(reliability, 0.85)

        final_score = (llm_score * 0.60) + (health_score * 0.40)

        if final_score >= 80:
            status = "Strong Buy"
        elif final_score >= 60:
            status = "Consider"
        else:
            status = "Avoid"

        c["final_score"] = round(final_score, 1)
        c["deal_status"] = status

        c["score_breakdown"] = {
            "strategy_score": llm_score,
            "health_score": int(health_score),
            "risk_penalty": reliability,
        }

        scored_leads.append(c)

    scored_leads.sort(key=lambda x: x["final_score"], reverse=True)

    print(
        f"   > Re-ranked {len(scored_leads)} leads. Top pick score: {scored_leads[0]['final_score']}"
    )

    return {"final_ranked_leads": scored_leads}

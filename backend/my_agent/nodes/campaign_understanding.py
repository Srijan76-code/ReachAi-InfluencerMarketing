from pydantic import BaseModel, Field
from typing import List, Literal
from core.model import model
from utils.state import LLMState


class CampaignContextModel(BaseModel):
    expanded_topics: List[str] = Field(
        description="5-7 specific YouTube content niches related to the core outcome. "
        "Example: If input is 'Python Course', output ['Python Roadmap 2025', 'Coding Interview Prep', 'System Design', 'Backend Development']"
    )

    target_video_formats: List[str] = Field(
        description="Visual styles that work best for this product. e.g., 'Tutorial', 'Unboxing', 'Case Study', 'Vlog'."
    )

    audience_pain_points: List[str] = Field(
        description="2-3 specific problems the audience is trying to solve. Used for semantic matching."
    )

    primary_value_driver: Literal[
        "views_volume", "engagement_depth", "creator_authority", "community_trust"
    ] = Field(
        description="The single most important metric for success. "
        "e.g., Low Ticket + Awareness -> 'views_volume'. "
        "High Ticket + Sales -> 'creator_authority'."
    )

    brand_safety_sensitivity: Literal["low", "medium", "high", "critical"] = Field(
        description="How risky can the content be? "
        "Gaming = Low, FinTech/Health = Critical."
    )


def campaign_understanding(state: LLMState):
    print("\n--- 0. CAMPAIGN STRATEGY & EXPANSION ---")

    context_model = model.with_structured_output(CampaignContextModel)

    brand = state["brand"]
    campaign = state["campaign"]
    audience = state["audience"]

    prompt = f"""
    You are a Senior YouTube Campaign Strategist.
    
    ### CLIENT PROFILE
    - **Brand:** {brand['name']} ({brand['industry']})
    - **Offer:** {brand['core_outcome']} (Price: {brand['product_price_range']})
    - **Target Audience:** {audience['target_persona']}
    - **Goal:** {campaign['goal']} (Creator Type: {campaign['creator_authority_level']})
    
    ### YOUR TASK
    1. **Expand Topics:** Don't just look for "{brand['industry']}". Look for the *specific niches* where this audience hangs out.
    2. **Define Strategy:** - If they are selling High Ticket items, prioritize 'Authority' and 'Tutorials'.
       - If they are selling Low Ticket/Apps, prioritize 'Views' and 'Reviews'.
    3. **Assess Safety:** - If FinTech/Health: Safety is 'Critical'.
       - If Gaming/Lifestyle: Safety is 'Low' or 'Medium'.

    Generate the campaign context configuration.
    """

    try:
        strategy_result = context_model.invoke(prompt)
        print(f"   [Strategy] Focus: {strategy_result.primary_value_driver}")
        print(f"   [Strategy] Topics: {strategy_result.expanded_topics[:3]}...")
    except Exception as e:
        print(f"[!] Strategy Generation Failed: {e}")
        return {
            "campaign_context": {
                "expanded_topics": [brand["industry"], "reviews", "tutorials"],
                "primary_value_driver": "engagement_depth",
                "brand_safety_sensitivity": "medium",
            }
        }

    full_context = {
        **brand,
        **audience,
        **campaign,
        "content_topics": strategy_result.expanded_topics,
        "video_formats": strategy_result.target_video_formats,
        "pain_points": strategy_result.audience_pain_points,
        "primary_metric": strategy_result.primary_value_driver,
        "safety_level": strategy_result.brand_safety_sensitivity,
    }

    return {"campaign_context": full_context}

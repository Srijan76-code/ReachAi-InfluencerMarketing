from typing import List
from pydantic import BaseModel, Field


from langchain_core.messages import SystemMessage, HumanMessage
from core.model import model
from utils.state import LLMState


class TargetedKeywords(BaseModel):
    topic_keywords: List[str] = Field(
        description="Direct searches for the subject matter"
    )
    pain_point_keywords: List[str] = Field(
        description="Searches based on specific struggles/questions"
    )
    cultural_keywords: List[str] = Field(description="Insider slang or community terms")
    format_keywords: List[str] = Field(
        description="Searches specifying the video format (e.g., 'tutorial')"
    )


def keyword_generator(state: LLMState):
    print("\n--- 1. KEYWORD GENERATION (Strategic) ---")
    ctx = state["campaign_context"]

    system_prompt = """
    You are a YouTube Search Query Expert. 
    Translate a Marketing Strategy into Native YouTube Search Terms.

    ### INSTRUCTION: Map Strategy to Search Behavior
    1. Look at 'Target Formats': If format is 'Tutorial', generate "How to..." queries.
    2. Look at 'Pain Points': If pain is 'Debugging', generate "Fixing X error..." queries.
    3. Look at 'Authority': 
       - Peer -> "My experience", "Truth about"
       - Expert -> "Analysis", "Future of", "Deep Dive"
    """

    expanded_topics = ctx.get("content_topics", [])
    formats = ctx.get("video_formats", [])
    pains = ctx.get("pain_points", [])

    user_prompt = f"""
    GENERATE KEYWORDS FOR THIS STRATEGY:
    
    1. Core Topics: {', '.join(expanded_topics)}
    2. Target Formats: {', '.join(formats)}
    3. Audience Pain Points: {', '.join(pains)}
    4. Persona/Vibe: {ctx.get('target_persona', 'General Audience')}
    
    OUTPUT: JSON with 4 lists (topic, pain_point, cultural, format).
    """

    generator = model.with_structured_output(TargetedKeywords)
    try:
        keywords_data = generator.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        )

        all_keywords = list(
            set(
                keywords_data.topic_keywords
                + keywords_data.pain_point_keywords
                + keywords_data.cultural_keywords
                + keywords_data.format_keywords
            )
        )

        print(
            f"   [Keywords] Generated {len(all_keywords)} queries (e.g., '{all_keywords[0]}')"
        )
        return {
            "search_keywords": all_keywords[:30],
            "keyword_debug": keywords_data.model_dump(),
        }

    except Exception as e:
        print(f"[!] Keyword Gen Failed: {e}")
        return {"search_keywords": expanded_topics[:10]}

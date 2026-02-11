from typing import Literal, TypedDict, Optional, List, Dict, Set, Any
from dotenv import load_dotenv
from itertools import product
from pydantic import BaseModel, Field


class ChannelData(TypedDict):
    id: str
    title: str
    description: str
    country: str
    uploads_id: str
    subscribers: int
    video_count: int
    estimated_cpm: float
    lifetime_health: float


class VideoStat(TypedDict):
    title: str
    views: int


class ChannelMetrics(TypedDict):
    avg_views: int
    volatility: float
    reliability: str
    engagement_rate: float
    raw_engagement: float
    trust_score: int
    forecast: str


class Socials(TypedDict):
    email: Optional[str]
    instagram: Optional[str]
    twitter: Optional[str]
    linkedin: Optional[str]


class EnrichedChannel(ChannelData):
    valuation: float
    rich_context: str
    socials: Socials

    metrics: ChannelMetrics
    recent_videos: List[VideoStat]


class AnalyzedChannel(EnrichedChannel):
    semantic_score: float


class RankedChannel(AnalyzedChannel):
    relevance_score: int
    llm_reasoning: str


class ScoreBreakdown(TypedDict):
    strategy_score: int
    health_score: int
    risk_penalty: str


class FinalScoredChannel(RankedChannel):
    final_score: float
    deal_status: str
    score_breakdown: ScoreBreakdown


class BrandDetails(TypedDict):
    name: str
    website: Optional[str]
    industry: str
    business_model: str
    product_price_range: str
    core_outcome: str


class AudienceDetails(TypedDict):
    target_persona: str
    locations: List[str]
    languages: List[str]


class ConstraintsDetails(TypedDict):
    min_subscribers: int
    max_subscribers: int
    target_countries: List[str]
    exclude_kids_content: bool


class CampaignDetails(TypedDict):
    goal: str
    creator_authority_level: str
    platform: str
    budget_total: int
    creator_count: int


class CampaignContext(TypedDict):
    brand: BrandDetails
    audience: AudienceDetails
    campaign: CampaignDetails

    content_topics: List[str]
    video_formats: List[str]
    pain_points: List[str]
    primary_metric: str
    safety_level: str


class LLMState(TypedDict, total=False):
    brand: BrandDetails
    campaign: CampaignDetails
    audience: AudienceDetails
    constraints: ConstraintsDetails

    campaign_context: CampaignContext
    search_keywords: List[str]
    keyword_debug: Dict

    candidate_channel_ids: List[str]
    filtered_channels: Dict[str, ChannelData]
    enriched_candidates: List[EnrichedChannel]
    analyzed_leads: List[AnalyzedChannel]
    re_ranked_leads: List[RankedChannel]
    final_ranked_leads: List[FinalScoredChannel]

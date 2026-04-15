from pydantic import BaseModel
from typing import List

class BrandInput(BaseModel):
    name: str
    website: str
    industry: str
    business_model: str
    product_price_range: str
    core_outcome: str

class AudienceInput(BaseModel):
    target_persona: str
    locations: List[str]
    languages: List[str]

class CampaignInput(BaseModel):
    goal: str
    creator_authority_level: str
    platform: str
    budget_total: int
    creator_count: int

class ConstraintsInput(BaseModel):
    min_subscribers: int
    max_subscribers: int
    target_countries: List[str]
    exclude_kids_content: bool

class CampaignGenerateRequest(BaseModel):
    brand: BrandInput
    audience: AudienceInput
    campaign: CampaignInput
    constraints: ConstraintsInput

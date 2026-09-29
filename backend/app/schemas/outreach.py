from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PersonalizationEvidence(BaseModel):
    evidence_id: str
    reason: str


class EmailPitch(BaseModel):
    subject: str
    body: str


class SocialPitch(BaseModel):
    body: str


class PitchBundle(BaseModel):
    creator_id: str
    pitch_angle: str
    personalization: List[PersonalizationEvidence] = Field(default_factory=list)
    email: Optional[EmailPitch] = None
    instagram: Optional[SocialPitch] = None
    twitter: Optional[SocialPitch] = None
    linkedin: Optional[SocialPitch] = None


class OutreachJobCreate(BaseModel):
    selected_creator_ids: List[str] = Field(default_factory=list)
    collaboration_type: Optional[str] = None
    deliverables: List[str] = Field(default_factory=list)
    creator_overrides: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class OutreachJobResponse(BaseModel):
    outreach_job_id: str
    campaign_id: str
    status: str


class OutreachPitchResponse(BaseModel):
    pitch_id: str
    creator_id: str
    status: str


class OutreachJobDetailResponse(OutreachJobResponse):
    selected_creator_ids: List[str] = Field(default_factory=list)
    creator_overrides: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    pitches: List[OutreachPitchResponse] = Field(default_factory=list)
    pitch_pack: Optional[Dict[str, Any]] = None
    generation_stats: Optional[Dict[str, Any]] = None
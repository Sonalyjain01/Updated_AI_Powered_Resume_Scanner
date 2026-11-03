from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone
import uuid

from scoring import ScoreBreakdown, SkillAssessment

def utc_now() -> datetime:
    """Current time as a timezone-aware UTC datetime"""
    return datetime.now(timezone.utc)

class ResumeAnalysisRequest(BaseModel):
    job_description: str = Field(..., description="Job description to match against")

class ExtractedData(BaseModel):
    skills: List[str] = Field(default=[], description="Extracted skills from resume")
    education: List[str] = Field(default=[], description="Education background")
    experience: List[str] = Field(default=[], description="Work experience")

class AIExtractionOutput(BaseModel):
    """Shape the model must return when extracting resume data"""
    skills: List[str]
    education: List[str]
    experience: List[str]

class AIMatchOutput(BaseModel):
    """Shape the model must return when scoring a resume against a job.

    The model rates each criterion; the overall score is computed from the user's weights.
    """
    skills_score: float = Field(..., ge=0, le=100)
    experience_score: float = Field(..., ge=0, le=100)
    education_score: float = Field(..., ge=0, le=100)
    required_skills: List[SkillAssessment] = Field(default_factory=list)
    analysis_summary: str = Field(..., min_length=1)

class ResumeAnalysisResponse(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    extracted_data: ExtractedData
    match_score: float = Field(..., ge=0, le=100, description="Match percentage")
    job_description: str
    analysis_summary: str
    breakdown: Optional[ScoreBreakdown] = Field(default=None, description="How the score was reached; absent for estimated (fallback) scores")
    is_fallback: bool = Field(default=False, description="True when keyword matching replaced the AI for any step")
    fallback_notice: Optional[str] = Field(default=None, description="Plain-language note shown to the user when is_fallback is true")
    ocr_used: bool = Field(default=False, description="True when the resume text was read from page images with OCR, which can miss or misread words")
    saved: bool = Field(default=True, description="False when the result could not be stored in scan history")
    org_id: str = Field(default="default", description="The organisation this scan belongs to")
    created_by: Optional[str] = Field(default=None, description="The user who ran it; absent when sign-in was not required")
    created_at: datetime = Field(default_factory=utc_now)

class JobError(BaseModel):
    status_code: int
    detail: str


class JobAccepted(BaseModel):
    job_id: str
    status: str
    status_url: str


class JobResponse(BaseModel):
    id: str
    status: str = Field(..., description="queued, running, succeeded or failed")
    filename: str
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    queue_position: Optional[int] = Field(default=None, description="Jobs ahead of this one; only while queued")
    scan_id: Optional[str] = None
    result: Optional[ResumeAnalysisResponse] = Field(default=None, description="The finished scan; present when succeeded")
    error: Optional[JobError] = Field(default=None, description="Why it failed; present when failed")


class ScanHistoryResponse(BaseModel):
    scans: List[ResumeAnalysisResponse]
    total_count: int

class HealthResponse(BaseModel):
    status: str
    message: str
    ai_service: str = "Connected"
    database: str = "Connected"
    virus_scanner: str = "Disabled"
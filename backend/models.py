from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid

class ResumeAnalysisRequest(BaseModel):
    job_description: str = Field(..., description="Job description to match against")

class ExtractedData(BaseModel):
    skills: List[str] = Field(default=[], description="Extracted skills from resume")
    education: List[str] = Field(default=[], description="Education background")
    experience: List[str] = Field(default=[], description="Work experience")

class ResumeAnalysisResponse(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    extracted_data: ExtractedData
    match_score: float = Field(..., ge=0, le=100, description="Match percentage")
    job_description: str
    analysis_summary: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ScanHistoryResponse(BaseModel):
    scans: List[ResumeAnalysisResponse]
    total_count: int

class HealthResponse(BaseModel):
    status: str
    message: str
    ai_service: str = "Connected"
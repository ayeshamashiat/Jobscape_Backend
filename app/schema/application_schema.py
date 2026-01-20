# app/schema/application_schema.py
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.models.application import ApplicationStatus


class ApplicationCreate(BaseModel):
    """Job seeker creates application"""
    job_id: UUID
    resume_id: UUID
    cover_letter: Optional[str] = Field(None, max_length=2000)


class ApplicationUpdate(BaseModel):
    """Job seeker updates their application"""
    cover_letter: Optional[str] = None
    status: Optional[ApplicationStatus] = None  # Only for withdrawal


class EmployerApplicationUpdate(BaseModel):
    """Employer updates application status"""
    status: ApplicationStatus
    employer_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    interview_scheduled_at: Optional[datetime] = None
    interview_location: Optional[str] = None
    interview_notes: Optional[str] = None


class ApplicationResponse(BaseModel):
    id: UUID
    job_id: UUID
    job_seeker_id: UUID
    resume_id: Optional[UUID]
    status: ApplicationStatus
    cover_letter: Optional[str]
    match_score: int
    skills_match: dict
    applied_at: datetime
    updated_at: datetime
    
    # Include job details for job seeker
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    
    # Include job seeker details for employer
    applicant_name: Optional[str] = None
    applicant_email: Optional[str] = None
    
    model_config = {"from_attributes": True}


class ApplicationDetailResponse(ApplicationResponse):
    """Detailed view with all fields"""
    employer_notes: Optional[str] = None
    interview_scheduled_at: Optional[datetime] = None
    interview_location: Optional[str] = None
    interview_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    rejected_at: Optional[datetime] = None


class ApplicationStatsResponse(BaseModel):
    """Statistics for employer"""
    total_applications: int
    pending: int
    reviewed: int
    shortlisted: int
    interview_scheduled: int
    accepted: int
    rejected: int

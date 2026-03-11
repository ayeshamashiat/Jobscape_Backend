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
    ats_score: Optional[int] = 0
    ats_report: Optional[dict] = None
    current_round: int = 0
    applied_at: datetime
    updated_at: datetime
    
    # Booked interview slot (FCFS pool system)
    booked_slot_id: Optional[UUID] = None
    booked_slot_datetime: Optional[datetime] = None
    booked_slot_duration_minutes: Optional[int] = None
    booked_slot_location: Optional[str] = None
    booked_slot_style: Optional[str] = None
    booked_slot_meeting_link: Optional[str] = None
    
    # Include job details for job seeker
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    
    # Include job seeker details for employer
    applicant_name: Optional[str] = None
    applicant_email: Optional[str] = None
    
    # Unified interview schedule ID
    interview_schedule_id: Optional[UUID] = None
    
    model_config = {"from_attributes": True}


class ApplicationDetailResponse(ApplicationResponse):
    """Detailed view with all fields"""
    employer_notes: Optional[str] = None
    interview_scheduled_at: Optional[datetime] = None
    interview_location: Optional[str] = None
    interview_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    rejected_at: Optional[datetime] = None

    # Fields moved to ApplicationResponse
    pass


class ApplicationStatsResponse(BaseModel):
    """Statistics for employer"""
    total_applications: int
    pending: int
    reviewed: int
    shortlisted: int
    interview_scheduled: int
    accepted: int
    rejected: int

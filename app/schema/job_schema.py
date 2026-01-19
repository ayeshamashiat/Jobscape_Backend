from pydantic import BaseModel, Field, field_validator, model_validator
from uuid import UUID
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from app.models.job import JobType, ExperienceLevel, WorkMode


class JobCreate(BaseModel):
    title: str
    description: str
    salary_min: int
    salary_max: int
    location: str
    work_mode: str  # WorkMode enum
    job_type: str   # JobType enum
    experience_level: str  # ExperienceLevel enum
    required_skills: list[str]
    preferred_skills: list[str]
    is_fresh_graduate_friendly: bool = False
    
    # Required deadline
    application_deadline: datetime = Field(
        ...,
        description="Last date/time to accept applications (in UTC or local timezone)"
    )
    
    @field_validator("application_deadline")
    @classmethod
    def validate_deadline(cls, v: datetime) -> datetime:
        """Ensure deadline is in the future and reasonable"""
        now = datetime.now(timezone.utc)
        
        # Convert to UTC if naive datetime
        if v.tzinfo is None:
            # Assume Bangladesh time (UTC+6)
            bd_tz = timezone(timedelta(hours=6))
            v = v.replace(tzinfo=bd_tz)
        
        # Must be at least 1 day in future
        if v <= now:
            raise ValueError("Application deadline must be in the future")
        
        # Must be within 90 days (prevent spam)
        max_deadline = now + timedelta(days=90)
        if v > max_deadline:
            raise ValueError("Application deadline cannot be more than 90 days in the future")
        
        return v
    
    @field_validator("title", "description", "location")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Validate that string fields are not empty"""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()
    
    @model_validator(mode='after')
    def validate_salary(self):
        """Validate salary_max >= salary_min"""
        if self.salary_max < self.salary_min:
            raise ValueError("salary_max must be greater than or equal to salary_min")
        return self


class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    location: Optional[str] = None
    work_mode: Optional[WorkMode] = None
    job_type: Optional[JobType] = None
    experience_level: Optional[ExperienceLevel] = None
    required_skills: Optional[List[str]] = None
    preferred_skills: Optional[List[str]] = None
    is_fresh_graduate_friendly: Optional[bool] = None
    is_active: Optional[bool] = None
    application_deadline: Optional[datetime] = None  # Allow updating deadline


class JobResponse(BaseModel):
    model_config = {"from_attributes": True}
    
    id: UUID
    employer_id: UUID
    title: str
    description: str
    salary_min: int
    salary_max: int
    location: str
    work_mode: str
    job_type: str
    experience_level: str
    required_skills: list[str]
    preferred_skills: list[str]
    is_fresh_graduate_friendly: bool
    is_active: bool
    is_closed: bool
    application_deadline: datetime
    closed_at: Optional[datetime] = None
    closure_reason: Optional[str] = None
    created_at: datetime
    
    # Computed fields - will be calculated after model creation
    days_until_deadline: Optional[int] = None
    is_deadline_passed: bool = False
    
    @model_validator(mode='after')
    def compute_deadline_fields(self):
        """Calculate deadline-related fields"""
        if self.application_deadline:
            now = datetime.now(timezone.utc)
            
            # Make deadline timezone-aware if not already
            deadline = self.application_deadline
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            
            # Calculate days until deadline
            delta = deadline - now
            self.days_until_deadline = max(0, delta.days)
            
            # Check if deadline passed
            self.is_deadline_passed = now >= deadline
        
        return self


class JobSearchResponse(BaseModel):
    items: List[JobResponse]
    total: int
    page: int
    pages: int
    has_next: bool
    has_prev: bool

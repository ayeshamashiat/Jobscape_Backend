from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from uuid import UUID
from datetime import datetime


class EmployerRegistrationCreate(BaseModel):
    """Complete employer registration after basic signup"""

    # Person info
    full_name: str = Field(..., min_length=1, max_length=200)
    job_title: str = Field(..., min_length=1, max_length=100)
    work_email: EmailStr

    # Company info
    company_name: str = Field(..., min_length=1, max_length=200)
    company_website: Optional[str] = None
    industry: str = Field(..., min_length=1, max_length=100)
    location: str = Field(..., min_length=1, max_length=200)
    company_size: Optional[str] = Field(None, pattern="^(1-10|11-50|51-200|201-500|500\+)$")
    description: Optional[str] = Field(None, max_length=1000)

    # Company type
    company_type: str = Field(
        ...,
        pattern="^(REGISTERED|STARTUP|FREELANCE|NGO|GOVERNMENT)$"
    )

    # Startup fields
    is_startup: bool = Field(default=False)
    startup_stage: Optional[str] = Field(None, pattern="^(Idea|MVP|Early Revenue|Growth)$")
    founded_year: Optional[int] = Field(None, ge=2000, le=2026)

    # Alternative verification
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None

    @validator('company_website')
    def validate_website(cls, v):
        if v and not v.startswith('http://') and not v.startswith('https://'):
            return f'https://{v}'
        return v


class EmployerProfileUpdate(BaseModel):
    """Update employer profile"""
    full_name: Optional[str] = None
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    company_email: Optional[EmailStr] = None
    company_website: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None


class EmployerProfileResponse(BaseModel):
    """Employer profile response"""
    id: UUID
    user_id: UUID

    # Person
    full_name: str
    job_title: Optional[str]
    work_email: str
    work_email_verified: bool  # NEW

    # Company
    company_name: str
    company_website: Optional[str]
    company_email: Optional[str]
    industry: str
    company_size: Optional[str]
    location: str
    description: Optional[str]
    logo_url: Optional[str]

    # Verification
    verification_tier: str
    verified_at: Optional[datetime]
    trust_score: int

    # Meta
    profile_completed: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VerificationApprovalRequest(BaseModel):
    """Admin approval/rejection"""
    admin_notes: str = Field(..., min_length=10, max_length=1000)


# ===== NEW: Work Email Verification Schemas =====

class WorkEmailVerificationConfirm(BaseModel):
    """Confirm work email with 6-digit code"""
    verification_code: str = Field(..., min_length=6, max_length=6, pattern="^[0-9]{6}$")


class WorkEmailVerificationStatusResponse(BaseModel):
    """Work email verification status"""
    work_email: str
    work_email_verified: bool
    verification_sent_at: Optional[datetime]
    code_expired: bool
    can_resend: bool
    verification_tier: str
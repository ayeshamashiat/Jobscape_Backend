from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime


class JobSeekerProfileBase(BaseModel):
    """Base schema for job seeker profile"""
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    location: Optional[str] = Field(None, max_length=255)
    professional_summary: Optional[str] = Field(None, max_length=1000)
    skills: Optional[List[str]] = Field(default_factory=list)
    experience: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    education: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    projects: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    certifications: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    awards: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    languages: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    volunteer_experience: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    publications: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    linkedin_url: Optional[str] = Field(None, max_length=255)
    github_url: Optional[str] = Field(None, max_length=255)
    portfolio_url: Optional[str] = Field(None, max_length=255)
    other_links: Optional[List[str]] = Field(default_factory=list)


class JobSeekerProfileCreate(JobSeekerProfileBase):
    """Schema for completing profile (first-time setup)"""
    full_name: str = Field(..., min_length=1, max_length=255)
    phone: str = Field(..., max_length=20)
    location: str = Field(..., max_length=255)
    professional_summary: str = Field(..., min_length=10, max_length=1000)
    skills: List[str] = Field(..., min_length=1)  # ✅ Changed from min_items


class JobSeekerProfileUpdate(JobSeekerProfileBase):
    """Schema for updating profile - all fields optional"""
    pass


class JobSeekerProfileResponse(BaseModel):
    """Schema for job seeker profile response"""
    id: UUID
    user_id: UUID
    full_name: str
    profile_picture_url: Optional[str]
    phone: Optional[str]
    location: Optional[str]
    professional_summary: Optional[str]
    inferred_industries: List[str]
    primary_industry: Optional[str]
    skills: List[str]
    experience: List[Dict[str, Any]]
    education: List[Dict[str, Any]]
    projects: List[Dict[str, Any]]
    certifications: List[Dict[str, Any]]
    awards: List[Dict[str, Any]]
    languages: List[Dict[str, Any]]
    volunteer_experience: List[Dict[str, Any]]
    publications: List[Dict[str, Any]]
    linkedin_url: Optional[str]
    github_url: Optional[str]
    portfolio_url: Optional[str]
    other_links: List[str]
    profile_completed: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ProfileCompletionStatus(BaseModel):
    """Schema for profile completion status"""
    is_completed: bool
    completion_percentage: float
    missing_required_fields: List[str]
    optional_fields_status: Dict[str, bool]
    total_required_fields: int
    completed_required_fields: int

from pydantic import BaseModel, EmailStr
from uuid import UUID
from typing import Optional

class EmployerProfileCreate(BaseModel):
    company_name: str
    company_email: EmailStr
    location: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None  # e.g., "1-10", "11-50", "51-200"
    description: Optional[str] = None

class EmployerProfileUpdate(BaseModel):
    company_name: Optional[str] = None
    company_email: Optional[EmailStr] = None
    location: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None

class EmployerProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    company_name: str
    company_email: str
    location: Optional[str]
    website: Optional[str]
    industry: Optional[str]
    size: Optional[str]
    description: Optional[str]
    logo_url: Optional[str]
    is_verified: bool

    class Config:
        from_attributes = True

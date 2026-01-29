# app/schema/coverletterschema.py
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class CoverLetterBase(BaseModel):
    """Base schema for cover letter"""
    title: str = Field(..., min_length=1, max_length=200, description="Title/name for this cover letter")
    content: str = Field(..., min_length=10, max_length=5000, description="Cover letter text content")


class CoverLetterCreate(CoverLetterBase):
    """Schema for creating a new cover letter"""
    pass


class CoverLetterUpdate(BaseModel):
    """Schema for updating a cover letter - all fields optional"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=10, max_length=5000)


class CoverLetterResponse(CoverLetterBase):
    """Schema for cover letter response"""
    id: UUID
    jobseeker_id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True  # For Pydantic v2 (was orm_mode in v1)


class CoverLetterListResponse(BaseModel):
    """Schema for list of cover letters with metadata"""
    items: list[CoverLetterResponse]
    total: int
    page: int
    
    class Config:
        from_attributes = True

from pydantic import BaseModel, validator
from uuid import UUID
from typing import List, Optional
from datetime import datetime
from app.models.job import JobType, ExperienceLevel, WorkMode

class JobCreate(BaseModel):
    title: str
    description: str
    salary_min: int
    salary_max: int
    location: str
    work_mode: WorkMode
    job_type: JobType
    experience_level: ExperienceLevel
    required_skills: List[str]
    preferred_skills: List[str] = []
    is_fresh_graduate_friendly: bool = False
    
    @validator('required_skills')
    def validate_required_skills(cls, v):
        if not v or len(v) == 0:
            raise ValueError('At least one required skill must be specified')
        return v
    
    @validator('salary_max')
    def validate_salary(cls, v, values):
        if 'salary_min' in values and v < values['salary_min']:
            raise ValueError('salary_max must be greater than or equal to salary_min')
        return v
    
    @validator('title', 'description', 'location')
    def validate_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Field cannot be empty')
        return v.strip()

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

class JobResponse(BaseModel):
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
    required_skills: List[str]
    preferred_skills: List[str]
    is_fresh_graduate_friendly: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class JobSearchResponse(BaseModel):
    items: List[JobResponse]
    total: int
    page: int
    pages: int
    has_next: bool
    has_prev: bool

import uuid
from typing import List, Optional
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, DateTime, Integer, func, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum

class JobType(str, enum.Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"

class ExperienceLevel(str, enum.Enum):
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"

class WorkMode(str, enum.Enum):
    REMOTE = "remote"
    ONSITE = "onsite"
    HYBRID = "hybrid"

class Job(Base):
    __tablename__ = "jobs"
    
    __table_args__ = (
        Index('idx_job_location', 'location'),
        Index('idx_job_is_active', 'is_active'),
        Index('idx_job_created_at', 'created_at'),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employers.id", ondelete="CASCADE"), nullable=False)
    
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Salary
    salary_min: Mapped[int] = mapped_column(Integer, nullable=False)
    salary_max: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Location & Work Mode
    location: Mapped[str] = mapped_column(String, nullable=False)
    work_mode: Mapped[WorkMode] = mapped_column(String, nullable=False)
    
    # Job Details
    job_type: Mapped[JobType] = mapped_column(String, nullable=False)
    experience_level: Mapped[ExperienceLevel] = mapped_column(String, nullable=False)
    
    # Skills
    required_skills: Mapped[List[str]] = mapped_column(JSONB, default=list, nullable=False)
    preferred_skills: Mapped[List[str]] = mapped_column(JSONB, default=list, nullable=False)
    
    # Flags
    is_fresh_graduate_friendly: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    employer = relationship(
        "Employer",
        back_populates="jobs"
    )

    applications = relationship(
        "Application",
        back_populates="job",
        cascade="all, delete-orphan"
    )

    application_deadline: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False  # ← REQUIRED!
    )
    
    # Status tracking
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closure_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # "deadline", "manual", "filled"
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

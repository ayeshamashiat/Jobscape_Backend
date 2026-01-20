import uuid
from typing import List, Optional
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, DateTime, func, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class JobSeeker(Base):
    __tablename__ = "job_seekers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    full_name: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    profile_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    
    profile_picture_url: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True
    )
    
    # Contact & Location
    phone: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True
    )
    
    location: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True
    )
    
    # Professional Info
    professional_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    # ===== INDUSTRY INFERENCE (NEW) =====
    inferred_industries: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="Industries parsed from resume"
    )
    
    primary_industry: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
        comment="Most relevant industry from CV"
    )

    # JSONB fields for structured data
    education: Mapped[List[dict]] = mapped_column(
        JSONB,
        default=list,
        nullable=False
    )

    experience: Mapped[List[dict]] = mapped_column(
        JSONB,
        default=list,
        nullable=False
    )

    skills: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False
    )
    
    projects: Mapped[List[dict]] = mapped_column(
        JSONB,
        default=list,
        nullable=False
    )
    
    certifications: Mapped[List[dict]] = mapped_column(
        JSONB,
        default=list,
        nullable=False
    )
    
    awards: Mapped[List[dict]] = mapped_column(
        JSONB,
        default=list,
        nullable=False
    )
    
    languages: Mapped[List[dict]] = mapped_column(
        JSONB,
        default=list,
        nullable=False
    )
    
    publications: Mapped[List[dict]] = mapped_column(
        JSONB,
        default=list,
        nullable=False
    )
    
    volunteer_experience: Mapped[List[dict]] = mapped_column(
        JSONB,
        default=list,
        nullable=False
    )
    
    # Social/Professional Links
    linkedin_url: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True
    )
    
    github_url: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True
    )
    
    portfolio_url: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True
    )
    
    other_links: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now()
    )

    # Relationships
    user = relationship(
        "User",
        back_populates="job_seeker_profile"
    )

    resumes = relationship(
        "Resume",
        back_populates="job_seeker",
        cascade="all, delete-orphan"
    )

    applications = relationship(
        "Application",
        back_populates="job_seeker",
        cascade="all, delete-orphan"
    )

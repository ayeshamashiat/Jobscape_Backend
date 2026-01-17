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

    # JSONB fields for structured data
    education: Mapped[List[dict]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="List of education entries with institution, degree, field, year"
    )

    experience: Mapped[List[dict]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="List of work experience with company, position, duration, description"
    )

    skills: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="List of technical and soft skills"
    )
    
    # New comprehensive fields
    projects: Mapped[List[dict]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="List of projects with title, description, technologies, links"
    )
    
    certifications: Mapped[List[dict]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="List of certifications with name, issuer, date, credential_id"
    )
    
    awards: Mapped[List[dict]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="List of awards/achievements with title, issuer, date, description"
    )
    
    languages: Mapped[List[dict]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="List of languages with name and proficiency level"
    )
    
    publications: Mapped[List[dict]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="List of publications/papers with title, journal, date, link"
    )
    
    volunteer_experience: Mapped[List[dict]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="List of volunteer work with organization, role, duration, description"
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
        nullable=False,
        comment="Other professional links (Behance, Dribbble, etc.)"
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
    user = relationship("User", backref="job_seeker", uselist=False)
    resumes = relationship("Resume", backref="job_seeker", cascade="all, delete-orphan")

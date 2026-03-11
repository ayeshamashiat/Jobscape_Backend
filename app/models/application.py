# app/models/application.py
from typing import Optional
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, DateTime, func, Text, Enum as SQLEnum
from sqlalchemy import Integer, String, Boolean, ForeignKey, DateTime, func, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum
from sqlalchemy.dialects.postgresql import JSONB



class ApplicationStatus(str, enum.Enum):
    PENDING = "PENDING"
    REVIEWED = "REVIEWED"
    SHORTLISTED = "SHORTLISTED"
    INTERVIEW_SCHEDULED = "INTERVIEW_SCHEDULED"
    REJECTED = "REJECTED"
    ACCEPTED = "ACCEPTED"
    HIRED = "HIRED"
    WITHDRAWN = "WITHDRAWN"


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False
    )

    job_seeker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_seekers.id", ondelete="CASCADE"),
        nullable=False
    )

    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resumes.id", ondelete="SET NULL"),
        nullable=True
    )

    # Application details
    status: Mapped[ApplicationStatus] = mapped_column(
        SQLEnum(ApplicationStatus),
        default=ApplicationStatus.PENDING,
        nullable=False
    )

    cover_letter: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )

    # Employer notes (visible only to employer)
    employer_notes: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )

    # AI matching score (0-100)
    match_score: Mapped[int] = mapped_column(
        default=0,
        nullable=False
    )

    # Skills match breakdown
    skills_match: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="{'matched': [...], 'missing': [...]}"
    )

    # Interview details
    interview_scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    interview_location: Mapped[str] = mapped_column(
        String,
        nullable=True
    )

    interview_notes: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )

    # Rejection details
    rejection_reason: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )

    rejected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Timestamps
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    # Ats score
    ats_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0–100
    ats_report: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # detailed breakdown

    # Selection Process Tracking
    current_round: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0 = Applied, 1-5 = Selection Rounds
    
    # Slot request tracking
    has_requested_extra_slots: Mapped[bool] = mapped_column(Boolean, default=False)



    # Relationships
    job = relationship("Job", back_populates="applications")
    job_seeker = relationship("JobSeeker", back_populates="applications")
    resume = relationship("Resume", back_populates="applications")
    
    booked_slot_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("interview_slot_pool.id", ondelete="SET NULL"),
        nullable=True
    )
    booked_slot = relationship("InterviewSlotPool", back_populates="applications")
    
    @property
    def booked_slot_datetime(self) -> Optional[datetime]:
        return self.booked_slot.datetime_utc if self.booked_slot else None

    @property
    def booked_slot_duration_minutes(self) -> Optional[int]:
        return self.booked_slot.duration_minutes if self.booked_slot else None

    @property
    def booked_slot_location(self) -> Optional[str]:
        return self.booked_slot.location if self.booked_slot else None

    @property
    def booked_slot_style(self) -> Optional[str]:
        return self.booked_slot.style if self.booked_slot else None

    @property
    def booked_slot_meeting_link(self) -> Optional[str]:
        return self.booked_slot.meeting_link if self.booked_slot else None

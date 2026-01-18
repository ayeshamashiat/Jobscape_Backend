import uuid
from typing import List, Optional
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, DateTime, func, Text, Integer, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.user import User
from app.models.job import Job


class Employer(Base):
    __tablename__ = "employers"

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

    # Person Info
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    job_title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    work_email: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    # Company Info

    company_name: Mapped[str] = mapped_column(String, nullable=False)
    company_email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    company_website: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    industry: Mapped[str] = mapped_column(String, nullable=False)
    company_size: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    location: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Verification
    verification_tier: Mapped[str] = mapped_column(String, nullable=False, default="UNVERIFIED")
    company_type: Mapped[str] = mapped_column(String, nullable=False, default="REGISTERED")
    is_startup: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    startup_stage: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    founded_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    rjsc_registration_number: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True)
    trade_license_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tin_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    verification_documents: Mapped[List[dict]] = mapped_column(JSONB, default=list, nullable=False)
    verification_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    verified_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    alternative_verification_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    alternative_verification_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    
    document_ai_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    document_ai_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    trust_score: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    reported_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    profile_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # ===== RELATIONSHIPS =====
    # ✅ SPECIFY foreign_keys TO AVOID AMBIGUITY
    user: Mapped["User"] = relationship(
        "User",
        back_populates="employer_profile",
        foreign_keys=[user_id]  # ← LIST FORMAT!
    )

    jobs = relationship(
        "Job",
        back_populates="employer",
        cascade="all, delete-orphan"
    )

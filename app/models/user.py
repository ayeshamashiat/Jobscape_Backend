import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum


if TYPE_CHECKING:
    from app.models.employer import Employer
    from app.models.job_seeker import JobSeeker


class UserRole(str, enum.Enum):
    JOB_SEEKER = "JOB_SEEKER"
    EMPLOYER = "EMPLOYER"
    ADMIN = "ADMIN"

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), nullable=False, default=UserRole.JOB_SEEKER)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # ✅ CHANGED: is_active now defaults to True
    # Only set to False if admin suspends account (not for registration flow)
    is_active: Mapped[bool] = mapped_column(
        Boolean, 
        default=True,  # ✅ Changed from False
        nullable=False,
        comment="False only if account is suspended by admin, not during registration"
    )
    
    # OAuth
    oauth_provider: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    oauth_provider_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    # Email Verification
    email_verification_token: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email_verification_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # ===== RELATIONSHIPS WITH EXPLICIT FOREIGN KEYS =====
    employer_profile: Mapped[Optional["Employer"]] = relationship(
        "Employer",
        back_populates="user",
        foreign_keys="Employer.user_id",  # STRING FORMAT
        uselist=False,
        cascade="all, delete-orphan"
    )

    job_seeker_profile: Mapped[Optional["JobSeeker"]] = relationship(
        "JobSeeker",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )

import uuid
import enum
from typing import Optional
from datetime import datetime
from sqlalchemy import String, Boolean, Enum as SQLEnum, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserRole(str, enum.Enum):
    JOB_SEEKER = "job_seeker"
    EMPLOYER = "employer"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    email: Mapped[str] = mapped_column(
        String,
        unique=True,
        index=True,
        nullable=False
    )

    hashed_password: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True
    )

    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, name="userrole"),
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    # Email Verification
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    
    email_verification_token: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True
    )
    
    email_verification_expiry: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )

    # OAuth
    oauth_provider: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True
    )

    oauth_provider_id: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True
    )

import uuid
from typing import List
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base



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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now()
    )

    # optional ORM relationship
    user = relationship("User", backref="job_seeker", uselist=False)
    resumes = relationship("Resume", backref="job_seeker")


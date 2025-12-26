import uuid
import enum
from typing import Optional

from sqlalchemy import String, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

class ResumeParseStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"

class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    job_seeker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_seekers.id", ondelete="CASCADE"),
        nullable=False
    )

    file_url: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    parsed_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True
    )

    parse_status: Mapped[ResumeParseStatus] = mapped_column(
        SQLEnum(ResumeParseStatus, name="resume_parse_status_enum"),
        default=ResumeParseStatus.PENDING,
        nullable=False
    )

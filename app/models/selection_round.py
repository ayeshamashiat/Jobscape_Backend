# app/models/selection_round.py
import uuid
from typing import List, Optional
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, Integer, func, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum


class RoundType(str, enum.Enum):
    SCREENING = 'screening'     # Initial HR screen
    TECHNICAL = 'technical'     # Technical/skill test
    INTERVIEW = 'interview'     # In-person or video interview
    ASSESSMENT = 'assessment'   # Written/task-based test
    FINAL = 'final'             # Final round / offer discussion


class SelectionProcess(Base):
    __tablename__ = 'selection_processes'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('jobs.id', ondelete='CASCADE'),
        nullable=False,
        unique=True
    )

    employer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('employers.id', ondelete='CASCADE'),
        nullable=False
    )

    # 1 to 3 rounds stored as JSONB array for simplicity.
    # Each round: {
    #   'number': int,
    #   'type': str,
    #   'title': str,
    #   'description': str,
    #   'duration_minutes': int,
    #   'is_online': bool,
    #   'location_or_link': str
    # }
    rounds: Mapped[List[dict]] = mapped_column(JSONB, default=list, nullable=False)

    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    job = relationship('Job', backref='selection_process', uselist=False)
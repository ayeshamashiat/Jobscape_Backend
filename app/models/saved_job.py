import uuid
from datetime import datetime
from sqlalchemy import ForeignKey, DateTime, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class SavedJob(Base):
    __tablename__ = "saved_jobs"
    __table_args__ = (
        UniqueConstraint('job_seeker_id', 'job_id', name='uq_saved_job_seeker'),
    )

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
    
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("jobs.id", ondelete="CASCADE"), 
        nullable=False
    )
    
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )

    # Relationships
    job_seeker = relationship("JobSeeker", back_populates="saved_jobs")
    job = relationship("Job", back_populates="saved_by")

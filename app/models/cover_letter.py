import uuid
from typing import List, Optional
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, DateTime, func, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

# app/models/cover_letter.py
class SavedCoverLetter(Base):
    __tablename__ = "saved_cover_letters"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jobseeker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("job_seekers.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String, nullable=False)  # e.g., "Software Engineer Cover Letter"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    jobseeker = relationship("JobSeeker", back_populates="saved_cover_letters")

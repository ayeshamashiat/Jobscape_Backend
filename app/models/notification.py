# app/models/notification.py
import uuid
import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, func, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class NotificationType(str, enum.Enum):
    SYSTEM = "SYSTEM"           # General system updates
    INTERVIEW = "INTERVIEW"    # Interview schedules, confirmed slots
    BROADCAST = "BROADCAST"    # Employer announcements
    APPLICATION = "APPLICATION" # Status changes (Shortlisted, Rejected, etc.)
    MESSAGE = "MESSAGE"         # Direct messages
    PROFILE_VIEW = "PROFILE_VIEW" # Employer viewed seeker profile

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType), 
        nullable=False, 
        default=NotificationType.SYSTEM
    )
    
    # Optional link to redirect within the app (e.g. /job-seeker/applications/[id])
    link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )

    # Relationship
    user = relationship("User", backref="notifications")

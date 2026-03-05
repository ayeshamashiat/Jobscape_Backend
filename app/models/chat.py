# app/models/chat.py
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, DateTime, Text, func, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum


class MessageStatus(str, enum.Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"


class ChatRoom(Base):
    """A chat room between an employer and a job seeker, tied to a specific application"""
    __tablename__ = "chat_rooms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        unique=True  # One chat room per application
    )

    employer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employers.id", ondelete="CASCADE"),
        nullable=False
    )

    job_seeker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_seekers.id", ondelete="CASCADE"),
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    messages = relationship("ChatMessage", back_populates="room", cascade="all, delete-orphan", order_by="ChatMessage.created_at")
    application = relationship("Application", backref="chat_room")
    employer = relationship("Employer", backref="chat_rooms")
    job_seeker = relationship("JobSeeker", backref="chat_rooms")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_rooms.id", ondelete="CASCADE"),
        nullable=False
    )

    # Sender info - either employer or job_seeker (one will be null)
    sender_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    
    sender_role: Mapped[str] = mapped_column(String, nullable=False)  # "employer" or "job_seeker"

    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    status: Mapped[MessageStatus] = mapped_column(
        String,
        default=MessageStatus.SENT,
        nullable=False
    )

    # Optional: attachment metadata
    attachment_url: Mapped[str] = mapped_column(String, nullable=True)
    attachment_type: Mapped[str] = mapped_column(String, nullable=True)  # "pdf", "image", etc.

    is_system_message: Mapped[bool] = mapped_column(Boolean, default=False)  # For automated status updates

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    room = relationship("ChatRoom", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_user_id])
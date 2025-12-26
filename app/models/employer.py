import uuid
from typing import Optional

from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

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

    company_name: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    company_email: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    location: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    website: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True
    )
    industry: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True
    )
    size: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True
    )
    description: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True
    )
    logo_url: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True
    )
    
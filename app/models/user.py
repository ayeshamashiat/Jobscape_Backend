from sqlalchemy import Column, String, Enum, Boolean
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.database import Base
import enum

class UserRole(str, enum.Enum):
    JOB_SEEKER = "job_seeker"
    EMPLOYER = "employer"
    ADMIN = "admin"

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=True)  # null if OAuth-only
    role = Column(Enum(UserRole), nullable=False)
    is_active = Column(Boolean, default=True)

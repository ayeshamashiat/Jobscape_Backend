from pydantic import BaseModel, EmailStr
from enum import Enum
from typing import Optional

class Role(str, Enum):
    JOB_SEEKER = "job_seeker"
    EMPLOYER = "employer"
    ADMIN = "admin"

class UserCreate(BaseModel):
    email: EmailStr
    password: Optional[str]  # required if email/password, optional for OAuth
    role: Role

class UserResponse(BaseModel):
    id: str
    email: str
    role: Role

    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

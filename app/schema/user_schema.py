from pydantic import BaseModel, EmailStr
from enum import Enum
from typing import Optional
from uuid import UUID
from app.models.user import UserRole

# ----------------- User creation -----------------
class UserCreate(BaseModel):
    email: EmailStr
    password: Optional[str]  # Can be None for OAuth users
    role: UserRole

# ----------------- User response -----------------
class UserResponse(BaseModel):
    id: UUID
    email: str
    role: UserRole
    is_active: bool
    is_email_verified: bool

    model_config = {
        "from_attributes": True
    }

# ----------------- Authentication tokens -----------------
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

# ----------------- Password reset -----------------
class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

# ----------------- Email verification -----------------
class EmailVerificationUpdate(BaseModel):
    is_email_verified: bool

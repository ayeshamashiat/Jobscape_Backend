from pydantic import BaseModel, EmailStr, Field
from enum import Enum
from typing import Optional
from uuid import UUID
from app.models.user import UserRole


# ----------------- User creation (for registration) -----------------
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=1, max_length=200)
    # Role is NOT here - it's set automatically by the route!

class JobSeekerBasicRegistration(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=1, max_length=200)

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
    new_password: str = Field(..., min_length=8)


# ----------------- Email verification -----------------
class EmailVerificationUpdate(BaseModel):
    is_email_verified: bool

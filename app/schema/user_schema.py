from pydantic import BaseModel, EmailStr
from enum import Enum
from typing import Optional
from app.models.user import UserRole

class UserCreate(BaseModel):
    email: EmailStr
    password: Optional[str]
    role: UserRole

class UserResponse(BaseModel):
    id: str
    email: str
    role: UserRole

    model_config = {
        "from_attributes": True
    }

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

# app/schema/auth_schema.py
from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from app.models.user import UserRole

# ----------------- Login -----------------
class LoginRequest(BaseModel):
    email: str
    password: str

# ----------------- Tokens -----------------
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[UUID] = None
    role: Optional[UserRole] = None

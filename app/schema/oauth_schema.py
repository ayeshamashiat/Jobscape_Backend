# app/schema/oauth_schema.py
from pydantic import BaseModel, EmailStr
from app.models.user import UserRole

class OAuthUserCreate(BaseModel):
    email: EmailStr
    role: UserRole
    provider: str
    provider_id: str

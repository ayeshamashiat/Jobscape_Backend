from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone
import uuid

from app.database import get_db
from app.utils.security import get_current_user
from app.models.chat import ChatRoom, ChatMessage, MessageStatus
from app.models.application import Application, ApplicationStatus
from app.models.user import User, UserRole

class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)


class MessageResponse(BaseModel):
    id: UUID
    room_id: UUID
    sender_user_id: UUID
    sender_role: str
    sender_name: str
    content: str
    status: str
    is_system_message: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class RoomResponse(BaseModel):
    id: UUID
    application_id: UUID
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    applicant_name: Optional[str] = None
    other_party_name: str
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None
    unread_count: int = 0
    is_active: bool

    model_config = {"from_attributes": True}
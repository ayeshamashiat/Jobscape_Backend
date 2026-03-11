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
from app.schema.chat_schema import (
    MessageCreate,
    MessageResponse,
    RoomResponse
)


def get_or_create_room(db: Session, application_id: UUID) -> ChatRoom:
    """Get existing chat room or create one for this application"""
    room = db.query(ChatRoom).filter(ChatRoom.application_id == application_id).first()
    if room:
        return room

    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # Only create chat rooms for applications that are at least REVIEWED
    if application.status == ApplicationStatus.PENDING:
        raise HTTPException(
            status_code=403,
            detail="Chat is only available after the employer has reviewed your application"
        )

    from app.models.job import Job
    from app.models.job_seeker import JobSeeker

    job = db.query(Job).filter(Job.id == application.job_id).first()

    room = ChatRoom(
        application_id=application_id,
        employer_id=job.employer_id,
        job_seeker_id=application.job_seeker_id,
        is_active=True
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return room
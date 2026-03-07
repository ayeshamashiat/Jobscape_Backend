# app/routes/chat_routes.py
"""
In-app chat between employers and job seekers.
Each chat room is tied to a specific application.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
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
import cloudinary
import cloudinary.uploader


router = APIRouter(prefix="/chat", tags=["chat"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)


class AttachmentInfo(BaseModel):
    url: str
    filename: str
    size: int
    type: str


class MessageResponse(BaseModel):
    id: UUID
    room_id: UUID
    sender_user_id: UUID
    sender_role: str
    sender_name: str
    content: str
    status: str
    is_system_message: bool
    attachments: List[AttachmentInfo] = []
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


# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_or_create_room(db: Session, application_id: UUID) -> ChatRoom:
    """Get existing chat room or create one for this application"""
    room = db.query(ChatRoom).filter(ChatRoom.application_id == application_id).first()
    if room:
        return room

    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if application.status == ApplicationStatus.PENDING:
        raise HTTPException(
            status_code=403,
            detail="Chat is only available after the employer has reviewed your application"
        )

    from app.models.job import Job

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


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.post("/rooms/{application_id}", response_model=dict)
def open_or_get_room(
    application_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    room = get_or_create_room(db, application_id)
    _verify_room_access(db, room, current_user)
    return {"room_id": str(room.id), "is_active": room.is_active}


@router.get("/rooms", response_model=List[RoomResponse])
def get_my_rooms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.employer import Employer
    from app.models.job_seeker import JobSeeker
    from app.models.job import Job

    if current_user.role == UserRole.EMPLOYER:
        employer = db.query(Employer).filter(Employer.user_id == current_user.id).first()
        if not employer:
            return []
        rooms = db.query(ChatRoom).filter(ChatRoom.employer_id == employer.id).all()
    else:
        seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
        if not seeker:
            return []
        rooms = db.query(ChatRoom).filter(ChatRoom.job_seeker_id == seeker.id).all()

    result = []
    for room in rooms:
        application = db.query(Application).filter(Application.id == room.application_id).first()
        job = db.query(Job).filter(Job.id == application.job_id).first() if application else None
        employer_obj = db.query(Employer).filter(Employer.id == room.employer_id).first()
        seeker_obj = db.query(JobSeeker).filter(JobSeeker.id == room.job_seeker_id).first()

        last_msg = (
            db.query(ChatMessage)
            .filter(ChatMessage.room_id == room.id)
            .order_by(desc(ChatMessage.created_at))
            .first()
        )

        if current_user.role == UserRole.EMPLOYER:
            other_party_name = seeker_obj.full_name if seeker_obj else "Applicant"
        else:
            other_party_name = employer_obj.company_name if employer_obj else "Employer"

        result.append(RoomResponse(
            id=room.id,
            application_id=room.application_id,
            job_title=job.title if job else None,
            company_name=employer_obj.company_name if employer_obj else None,
            applicant_name=seeker_obj.full_name if seeker_obj else None,
            other_party_name=other_party_name,
            last_message=last_msg.content if last_msg else None,
            last_message_at=last_msg.created_at if last_msg else None,
            is_active=room.is_active
        ))

    return result


@router.get("/rooms/{room_id}/messages", response_model=List[MessageResponse])
def get_messages(
    room_id: UUID,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.employer import Employer
    from app.models.job_seeker import JobSeeker

    room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    _verify_room_access(db, room, current_user)

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.room_id == room_id)
        .order_by(ChatMessage.created_at.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    result = []
    for msg in messages:
        if msg.sender_role == "employer":
            emp = db.query(Employer).filter(Employer.user_id == msg.sender_user_id).first()
            sender_name = emp.company_name if emp else "Employer"
        else:
            seeker = db.query(JobSeeker).filter(JobSeeker.user_id == msg.sender_user_id).first()
            sender_name = seeker.full_name if seeker else "Applicant"

        result.append(MessageResponse(
            id=msg.id,
            room_id=msg.room_id,
            sender_user_id=msg.sender_user_id,
            sender_role=msg.sender_role,
            sender_name=sender_name,
            content=msg.content,
            status=msg.status,
            is_system_message=msg.is_system_message,
            attachments=[AttachmentInfo(**a) for a in (msg.attachments or [])],
            created_at=msg.created_at
        ))

    return result


@router.post("/rooms/{room_id}/messages", response_model=MessageResponse)
def send_message(
    room_id: UUID,
    body: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send a message in a room"""
    room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if not room.is_active:
        raise HTTPException(status_code=403, detail="This conversation is no longer active")

    _verify_room_access(db, room, current_user)
    user_role = _get_user_role_in_room(db, room, current_user)

    msg = ChatMessage(
        room_id=room_id,
        sender_user_id=current_user.id,
        sender_role=user_role,
        content=body.content,
        status=MessageStatus.SENT,
        attachments=[]
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    from app.models.employer import Employer
    from app.models.job_seeker import JobSeeker

    if user_role == "employer":
        emp = db.query(Employer).filter(Employer.user_id == current_user.id).first()
        sender_name = emp.company_name if emp else "Employer"
    else:
        seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
        sender_name = seeker.full_name if seeker else "Applicant"

    return MessageResponse(
        id=msg.id,
        room_id=msg.room_id,
        sender_user_id=msg.sender_user_id,
        sender_role=msg.sender_role,
        sender_name=sender_name,
        content=msg.content,
        status=msg.status,
        is_system_message=msg.is_system_message,
        attachments=[],
        created_at=msg.created_at
    )


# ===== NEW: Feature 1.3 — Attachment upload =====
@router.post("/messages/{message_id}/attachments")
async def upload_attachment(
    message_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload a file attachment to an existing message."""
    MAX_SIZE_MB = 10
    ALLOWED_TYPES = [
        'image/jpeg', 'image/png', 'image/gif',
        'application/pdf', 'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ]

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, 'File type not allowed')

    content = await file.read()
    if len(content) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, f'File too large. Max {MAX_SIZE_MB}MB')

    # Verify the message exists and the user has access to its room
    msg = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
    if not msg:
        raise HTTPException(404, 'Message not found')

    room = db.query(ChatRoom).filter(ChatRoom.id == msg.room_id).first()
    _verify_room_access(db, room, current_user)

    # Upload to Cloudinary
    result = cloudinary.uploader.upload(
        content,
        resource_type='auto',
        folder='jobscape/chat_attachments'
    )

    # Append to attachments JSONB
    new_attachments = list(msg.attachments or [])
    new_attachments.append({
        'url': result['secure_url'],
        'filename': file.filename,
        'size': len(content),
        'type': file.content_type
    })
    msg.attachments = new_attachments
    db.commit()

    return {'url': result['secure_url'], 'filename': file.filename}


# ─── Private Helpers ──────────────────────────────────────────────────────────

def _get_user_role_in_room(db: Session, room: ChatRoom, user: User) -> str:
    from app.models.employer import Employer
    from app.models.job_seeker import JobSeeker

    emp = db.query(Employer).filter(Employer.user_id == user.id, Employer.id == room.employer_id).first()
    if emp:
        return "employer"
    seeker = db.query(JobSeeker).filter(JobSeeker.user_id == user.id, JobSeeker.id == room.job_seeker_id).first()
    if seeker:
        return "job_seeker"
    raise HTTPException(status_code=403, detail="Access denied")


def _verify_room_access(db: Session, room: ChatRoom, user: User):
    _get_user_role_in_room(db, room, user)  # Raises if no access
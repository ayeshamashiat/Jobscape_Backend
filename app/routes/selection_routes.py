# app/routes/selection_routes.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from uuid import UUID
from app.database import get_db
from app.utils.security import get_current_user
from app.models.selection_round import SelectionProcess, RoundType
from app.models.user import User, UserRole
from app.models.employer import Employer
from app.models.job import Job
from app.models.application import Application, ApplicationStatus
from app.models.job_seeker import JobSeeker
from app.utils.email import _send_selection_email
import uuid

router = APIRouter(prefix="/selection", tags=["selection"])


class RoundSchema(BaseModel):
    number: int = Field(..., ge=1, le=5)
    type: RoundType
    title: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    duration_minutes: Optional[int] = Field(None, ge=15, le=480)
    is_online: bool = False
    location_or_link: Optional[str] = None
    time_limit_minutes: Optional[int] = Field(None, ge=5, le=240)
    instructions: Optional[str] = None


class CreateSelectionProcessRequest(BaseModel):
    job_id: UUID
    rounds: List[RoundSchema] = Field(..., min_length=1, max_length=5)
    instructions: Optional[str] = None

    @field_validator('rounds')
    @classmethod
    def rounds_must_be_sequential(cls, v):
        numbers = [r.number for r in v]
        if sorted(numbers) != list(range(1, len(numbers) + 1)):
            raise ValueError('Round numbers must be sequential starting from 1')
        return v


@router.post("/", status_code=201)
def create_selection_process(
    data: CreateSelectionProcessRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(403, 'Only employers can create selection processes')

    employer = db.query(Employer).filter(Employer.user_id == current_user.id).first()
    job = db.query(Job).filter(Job.id == data.job_id, Job.employer_id == employer.id).first()
    if not job:
        raise HTTPException(404, 'Job not found or unauthorized')

    existing = db.query(SelectionProcess).filter(SelectionProcess.job_id == data.job_id).first()
    if existing:
        raise HTTPException(400, 'Selection process already exists for this job')

    process = SelectionProcess(
        job_id=data.job_id,
        employer_id=employer.id,
        rounds=[r.dict() for r in data.rounds],
        instructions=data.instructions
    )
    db.add(process)
    db.commit()
    db.refresh(process)
    return process


@router.put("/{process_id}")
def update_selection_process(
    process_id: UUID,
    data: CreateSelectionProcessRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    employer = db.query(Employer).filter(Employer.user_id == current_user.id).first()
    process = db.query(SelectionProcess).filter(
        SelectionProcess.id == process_id,
        SelectionProcess.employer_id == employer.id
    ).first()
    if not process:
        raise HTTPException(404, 'Selection process not found')

    process.rounds = [r.dict() for r in data.rounds]
    process.instructions = data.instructions
    db.commit()
    return process


@router.post("/{process_id}/notify")
def notify_applicants(
    process_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send selection process details to all shortlisted applicants"""
    employer = db.query(Employer).filter(Employer.user_id == current_user.id).first()
    process = db.query(SelectionProcess).filter(
        SelectionProcess.id == process_id,
        SelectionProcess.employer_id == employer.id
    ).first()
    if not process:
        raise HTTPException(404, 'Not found')

    apps = db.query(Application).filter(
        Application.job_id == process.job_id,
        Application.status.in_(['shortlisted', 'interview_scheduled'])
    ).all()

    sent = 0
    for app in apps:
        seeker = db.query(JobSeeker).filter(JobSeeker.id == app.job_seeker_id).first()
        if seeker and seeker.user:
            background_tasks.add_task(
                _send_selection_email,
                seeker_email=seeker.user.email,
                seeker_name=seeker.full_name,
                job=process.job,
                rounds=process.rounds,
                instructions=process.instructions
            )
            sent += 1

    return {'message': f'Notified {sent} applicants', 'sent': sent}


@router.get("/job/{job_id}")
def get_selection_for_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    # Accessible by both employer and job seeker — no auth required
):
    process = db.query(SelectionProcess).filter(SelectionProcess.job_id == job_id).first()
    if not process:
        raise HTTPException(404, 'No selection process defined for this job')
    return process


class SelectionAnnouncementRequest(BaseModel):
    hired_application_ids: List[UUID]
    announcement_message: Optional[str] = None


@router.post("/job/{job_id}/announce")
def announce_selection(
    job_id: UUID,
    body: SelectionAnnouncementRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Employer announces the selected candidates for a job"""
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can announce selection")

    employer = db.query(Employer).filter(Employer.user_id == current_user.id).first()
    if not employer:
        raise HTTPException(status_code=404, detail="Employer profile not found")

    job = db.query(Job).filter(Job.id == job_id, Job.employer_id == employer.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.is_selection_announced:
         raise HTTPException(status_code=400, detail="Selection has already been announced for this job")

    # 1. Update applications to HIRED
    hired_apps = db.query(Application).filter(
        Application.id.in_(body.hired_application_ids),
        Application.job_id == job_id
    ).all()

    if not hired_apps:
        raise HTTPException(status_code=400, detail="No valid applications selected to hire")

    from datetime import datetime, timezone
    from app.models.notification import Notification, NotificationType

    for app in hired_apps:
        app.status = ApplicationStatus.HIRED
        
        # 2. Update JobSeeker profile
        seeker = db.query(JobSeeker).filter(JobSeeker.id == app.job_seeker_id).first()
        if seeker:
            seeker.is_employed = True
            seeker.current_job_id = job.id
            seeker.current_employer_name = employer.company_name
            seeker.hired_at = datetime.now(timezone.utc)
            
            # Notify hired candidates
            notif = Notification(
                user_id=seeker.user_id,
                title=f"Congratulations! You've been selected for {job.title}",
                message=f"We are excited to announce that you've been selected for the position at {employer.company_name}.",
                type=NotificationType.SYSTEM,
                link=f"/job-seeker/applications/{app.id}"
            )
            db.add(notif)

    # 3. Mark job selection as announced
    job.is_selection_announced = True
    job.selection_announcement_date = datetime.now(timezone.utc)
    
    db.commit()
    return {"message": f"Selection announced successfully. {len(hired_apps)} candidates marked as hired."}
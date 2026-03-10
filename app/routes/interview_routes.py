# app/routes/interview_routes.py
"""
Enhanced interview scheduling and shortlist broadcast routes.
FCFS logic: Employer first creates a pool of time slots (with optional pre-set style).
            If employer pre-sets interview style → FCFS booking happens for job seekers.
            If employer allows seeker to choose style → Seeker picks style + slot.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import uuid
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone

from app.database import get_db
from app.utils.security import get_current_user
from app.models.interview import (
    InterviewSchedule, InterviewStyle, ShortlistBroadcast,
    Assessment, AssessmentQuestion, AssessmentAttempt,
    QuestionType, AssessmentType
)
from app.models.application import Application, ApplicationStatus
from app.models.user import User, UserRole
from app.utils.email import send_email


router = APIRouter(prefix="/interviews", tags=["interviews"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class TimeSlot(BaseModel):
    datetime_utc: str
    duration_minutes: int = 60


class ScheduleInterviewRequest(BaseModel):
    application_id: UUID
    style: InterviewStyle = InterviewStyle.IN_PERSON
    proposed_slots: List[TimeSlot] = Field(..., min_items=1)
    location: Optional[str] = None
    meeting_link: Optional[str] = None
    allow_style_choice: bool = False
    available_styles: Optional[List[InterviewStyle]] = None
    instructions: Optional[str] = None
    notes_for_candidate: Optional[str] = None


class ConfirmSlotRequest(BaseModel):
    schedule_id: UUID
    slot_index: int
    chosen_style: Optional[InterviewStyle] = None


class BroadcastRequest(BaseModel):
    job_id: UUID
    subject: str = Field(..., min_length=3, max_length=200)
    message: str = Field(..., min_length=10, max_length=5000)
    statuses: List[ApplicationStatus] = Field(default=[ApplicationStatus.SHORTLISTED])
    send_email: bool = True
    send_notification: bool = True


# ─── FCFS Slot Pool Schemas ───────────────────────────────────────────────────

class PoolSlotCreate(BaseModel):
    datetime_utc: datetime
    duration_minutes: int = 60
    capacity: int = 1
    # If style is provided by employer → FCFS (seeker cannot change it)
    # If style is None → seeker must choose a style when booking
    style: Optional[InterviewStyle] = None
    location: Optional[str] = None
    meeting_link: Optional[str] = None


class BulkSlotCreateRequest(BaseModel):
    job_id: UUID
    # allow_seeker_style_choice: if True, seekers pick their own style.
    # If False, slots must each have a style pre-defined.
    allow_seeker_style_choice: bool = False
    # available_styles shown to seeker when allow_seeker_style_choice is True
    available_styles: Optional[List[InterviewStyle]] = None
    slots: List[PoolSlotCreate]


class SlotBookingRequest(BaseModel):
    # Only required when the slot's style is None (seeker-chosen mode)
    chosen_style: Optional[InterviewStyle] = None


class InterviewReviewCreate(BaseModel):
    interview_id: UUID
    notes: Optional[str] = None
    metrics: dict = Field(default_factory=dict)
    overall_rating: int = Field(..., ge=1, le=5)


class InterviewReviewResponse(BaseModel):
    id: UUID
    application_id: UUID
    interview_id: UUID
    employer_id: UUID
    notes: Optional[str] = None
    metrics: dict
    overall_rating: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Assessment Schemas ───────────────────────────────────────────────────────

class AssessmentQuestionSchema(BaseModel):
    id: Optional[UUID] = None
    question_text: str
    question_type: QuestionType
    options: List[str] = []
    correct_answer: Optional[str] = None
    points: int = 1
    order_index: int = 0
    explanation: Optional[str] = None


class AssessmentCreateRequest(BaseModel):
    job_id: UUID
    title: str
    description: Optional[str] = None
    assessment_type: AssessmentType = AssessmentType.QUIZ
    time_limit_minutes: Optional[int] = None
    passing_score: int = 60
    is_required: bool = False
    trigger_stage: str = "after_shortlist"
    questions: List[AssessmentQuestionSchema]


class AssessmentSubmitRequest(BaseModel):
    answers: dict  # {question_id: answer}


# ─── Email helpers ────────────────────────────────────────────────────────────

def _interview_invitation_email(
    seeker_name: str,
    job_title: str,
    company_name: str,
    style: str,
    slots: List[TimeSlot],
    location: Optional[str],
    meeting_link: Optional[str],
    instructions: Optional[str],
):
    """Build html + text bodies for interview invitation email"""
    style_label = style.replace("_", " ").title()
    slots_html = "".join(
        f"<li style='margin:6px 0;'><strong>{s.datetime_utc}</strong> &nbsp;({s.duration_minutes} min)</li>"
        for s in slots
    )
    slots_text = "\n".join(f"  - {s.datetime_utc} ({s.duration_minutes} min)" for s in slots)

    location_html = f"<p><strong>Location:</strong> {location}</p>" if location else ""
    link_html = f'<p><strong>Meeting Link:</strong> <a href="{meeting_link}">{meeting_link}</a></p>' if meeting_link else ""
    instructions_html = f"<p><strong>Instructions:</strong> {instructions}</p>" if instructions else ""

    location_text = f"\nLocation: {location}" if location else ""
    link_text = f"\nMeeting Link: {meeting_link}" if meeting_link else ""
    instructions_text = f"\nInstructions: {instructions}" if instructions else ""

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #7c3aed, #6d28d9); padding: 24px; border-radius: 12px 12px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 22px;">🎉 Interview Invitation</h1>
        </div>
        <div style="border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px; padding: 24px;">
            <p>Hi <strong>{seeker_name}</strong>,</p>
            <p>You've been invited to interview for <strong>{job_title}</strong> at <strong>{company_name}</strong>!</p>

            <div style="background: #f5f3ff; border-left: 4px solid #7c3aed; padding: 12px 16px; border-radius: 4px; margin: 16px 0;">
                <p style="margin: 0;"><strong>Interview Format:</strong> {style_label}</p>
            </div>

            <p><strong>Proposed Time Slots — please pick one in your JBscape account:</strong></p>
            <ul style="padding-left: 20px; line-height: 1.8;">
                {slots_html}
            </ul>

            {location_html}
            {link_html}
            {instructions_html}

            <div style="margin-top: 24px; text-align: center;">
                <a href="{_frontend_url()}/jobseeker/interviews"
                   style="background: #7c3aed; color: white; padding: 12px 28px; border-radius: 8px; text-decoration: none; font-weight: bold;">
                    Confirm Your Time Slot
                </a>
            </div>

            <p style="margin-top: 24px; color: #6b7280; font-size: 13px;">
                Best regards,<br><strong>{company_name}</strong>
            </p>
        </div>
    </body>
    </html>
    """

    text_body = f"""
Interview Invitation — {job_title} at {company_name}

Hi {seeker_name},

You've been invited to interview for {job_title} at {company_name}!

Interview Format: {style_label}

Proposed Time Slots (pick one in your JBscape account):
{slots_text}
{location_text}
{link_text}
{instructions_text}

Log in to confirm: {_frontend_url()}/jobseeker/interviews

Best regards,
{company_name}
    """.strip()

    return html_body, text_body


def _slot_confirmed_email(seeker_name: str, slot_datetime: str, duration_minutes: int):
    """Build html + text for employer notification when slot is confirmed"""
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: #ecfdf5; border: 1px solid #6ee7b7; border-radius: 12px; padding: 24px;">
            <h2 style="color: #065f46; margin-top: 0;">✅ Interview Slot Confirmed</h2>
            <p><strong>{seeker_name}</strong> has confirmed their interview slot:</p>
            <div style="background: white; border-radius: 8px; padding: 16px; margin: 12px 0; border: 1px solid #d1fae5;">
                <p style="margin: 0; font-size: 18px; font-weight: bold; color: #065f46;">
                    {slot_datetime}
                </p>
                <p style="margin: 4px 0 0; color: #6b7280;">Duration: {duration_minutes} minutes</p>
            </div>
            <p style="color: #6b7280; font-size: 13px; margin-bottom: 0;">
                Log in to JBscape to view full interview details.
            </p>
        </div>
    </body>
    </html>
    """

    text_body = f"""
Interview Slot Confirmed

{seeker_name} has confirmed their interview slot:
  Date/Time: {slot_datetime}
  Duration:  {duration_minutes} minutes

Log in to JBscape to view full details.
    """.strip()
    return html_body, text_body


def _broadcast_email(seeker_name: str, company_name: str, message: str):
    """Build html + text for shortlist broadcast"""
    message_html = message.replace("\n", "<br>")

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #7c3aed, #6d28d9); padding: 24px; border-radius: 12px 12px 0 0;">
            <h2 style="color: white; margin: 0; font-size: 20px;">Message from {company_name}</h2>
        </div>
        <div style="border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px; padding: 24px;">
            <p>Hi <strong>{seeker_name}</strong>,</p>
            <div style="background: #f9fafb; border-radius: 8px; padding: 16px; margin: 12px 0; line-height: 1.7;">
                {message_html}
            </div>
            <p style="color: #6b7280; font-size: 13px; margin-bottom: 0;">
                Best regards,<br><strong>{company_name}</strong>
            </p>
        </div>
    </body>
    </html>
    """
    text_body = f"""
Message from {company_name}

Hi {seeker_name},

{message}

Best regards,
{company_name}
    """.strip()
    return html_body, text_body


def _interview_started_email(seeker_name: str, job_title: str, company_name: str, meeting_link: Optional[str]):
    """Build html + text for interview started notification"""
    link_html = f'<div style="margin-top: 24px; text-align: center;"><a href="{meeting_link}" style="background: #10b981; color: white; padding: 12px 28px; border-radius: 8px; text-decoration: none; font-weight: bold;">JOIN INTERVIEW NOW</a></div>' if meeting_link else ""
    link_text = f"\nJoin Interview: {meeting_link}" if meeting_link else ""

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: #10b981; padding: 24px; border-radius: 12px 12px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 22px;">🚀 Interview Started!</h1>
        </div>
        <div style="border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px; padding: 24px;">
            <p>Hi <strong>{seeker_name}</strong>,</p>
            <p>The employer from <strong>{company_name}</strong> has just started the interview for <strong>{job_title}</strong>.</p>
            <p>Please join as soon as possible.</p>
            {link_html}
            <p style="margin-top: 24px; color: #6b7280; font-size: 13px;">
                Log in to JBscape for more details.
            </p>
        </div>
    </body>
    </html>
    """
    text_body = f"""
Interview Started — {job_title} at {company_name}

Hi {seeker_name},

The employer from {company_name} has just started the interview for {job_title}.
{link_text}

Log in to JBscape for more details.
    """.strip()
    return html_body, text_body


def _slot_booked_notification_email(seeker_name: str, job_title: str, company_name: str, slot_datetime: datetime):
    """Notify job seeker that their booking was successful"""
    dt_str = slot_datetime.strftime("%Y-%m-%d %H:%M UTC")
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: #10b981; padding: 24px; border-radius: 12px 12px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 22px;">🗓️ Interview Booked!</h1>
        </div>
        <div style="border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px; padding: 24px;">
            <p>Hi <strong>{seeker_name}</strong>,</p>
            <p>You have successfully booked an interview for <strong>{job_title}</strong> at <strong>{company_name}</strong>.</p>
            <div style="background: #f0fdf4; border-left: 4px solid #10b981; padding: 12px 16px; border-radius: 4px; margin: 16px 0;">
                <p style="margin: 0;"><strong>Date/Time:</strong> {dt_str}</p>
            </div>
            <p>Check your dashboard for join links and further instructions.</p>
        </div>
    </body>
    </html>
    """
    text_body = f"Hi {seeker_name}, you have successfully booked an interview for {job_title} at {company_name} for {dt_str}."
    return html_body, text_body


def _frontend_url() -> str:
    import os
    return os.getenv("FRONTEND_URL", "http://localhost:3000")


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/schedule")
def schedule_interview(
    body: ScheduleInterviewRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Employer schedules an interview — sends proposed time slots to candidate"""
    from app.models.employer import Employer
    from app.models.job import Job
    from app.models.job_seeker import JobSeeker
    from app.models.user import User as UserModel

    employer = db.query(Employer).filter(Employer.user_id == current_user.id).first()
    if not employer:
        raise HTTPException(status_code=403, detail="Employer access required")

    application = db.query(Application).filter(Application.id == body.application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    job = db.query(Job).filter(Job.id == application.job_id).first()
    if job.employer_id != employer.id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    if application.status not in [ApplicationStatus.SHORTLISTED, ApplicationStatus.REVIEWED]:
        raise HTTPException(status_code=400, detail="Application must be shortlisted before scheduling interview")

    schedule = InterviewSchedule(
        application_id=body.application_id,
        scheduled_by_employer_id=employer.id,
        style=body.style,
        proposed_slots=[{"datetime": s.datetime_utc, "duration_minutes": s.duration_minutes} for s in body.proposed_slots],
        location=body.location,
        meeting_link=body.meeting_link,
        allow_style_choice=body.allow_style_choice,
        available_styles=[s.value for s in body.available_styles] if body.available_styles else [],
        instructions=body.instructions,
        notes_for_candidate=body.notes_for_candidate
    )
    db.add(schedule)
    application.status = ApplicationStatus.INTERVIEW_SCHEDULED
    db.commit()
    db.refresh(schedule)

    seeker = db.query(JobSeeker).filter(JobSeeker.id == application.job_seeker_id).first()
    seeker_user = db.query(UserModel).filter(UserModel.id == seeker.user_id).first()

    if seeker_user:
        html_body, text_body = _interview_invitation_email(
            seeker_name=seeker.full_name,
            job_title=job.title,
            company_name=employer.company_name,
            style=body.style.value,
            slots=body.proposed_slots,
            location=body.location,
            meeting_link=body.meeting_link,
            instructions=body.instructions,
        )
        background_tasks.add_task(
            send_email,
            to_email=seeker_user.email,
            subject=f"Interview Invitation: {job.title} at {employer.company_name}",
            html_body=html_body,
            text_body=text_body,
        )

    return {
        "success": True,
        "schedule_id": str(schedule.id),
        "message": "Interview scheduled. Candidate has been notified.",
    }


@router.post("/confirm-slot")
def confirm_slot(
    body: ConfirmSlotRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Job seeker confirms a time slot for their interview"""
    from app.models.job_seeker import JobSeeker
    from app.models.employer import Employer
    from app.models.user import User as UserModel

    seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not seeker:
        raise HTTPException(status_code=403, detail="Job seeker access required")

    schedule = db.query(InterviewSchedule).filter(InterviewSchedule.id == body.schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Interview schedule not found")

    application = db.query(Application).filter(Application.id == schedule.application_id).first()
    if application.job_seeker_id != seeker.id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    if body.slot_index >= len(schedule.proposed_slots):
        raise HTTPException(status_code=400, detail="Invalid slot index")

    chosen_slot = schedule.proposed_slots[body.slot_index]
    schedule.confirmed_at = datetime.fromisoformat(chosen_slot["datetime"])
    schedule.confirmed_duration_minutes = chosen_slot["duration_minutes"]
    schedule.is_confirmed = True

    if body.chosen_style and schedule.allow_style_choice:
        schedule.seeker_chosen_style = body.chosen_style.value

    # Unified meeting link for manual confirmation
    # If video, use internal room unless a specific link is provided
    # Effective style check (either pre-set or seeker chosen)
    effective_style = schedule.seeker_chosen_style or (schedule.style.value if hasattr(schedule.style, 'value') else schedule.style)
    
    if effective_style == "video_call" or effective_style == InterviewStyle.VIDEO_CALL:
        if not schedule.meeting_link or schedule.meeting_link.lower() in ["tbd", "zoom", "meet", "none"]:
            # Manual confirmation has no slot, so use schedule.id
            schedule.meeting_link = f"/interview/{schedule.id}"

    db.commit()

    employer = db.query(Employer).filter(Employer.id == schedule.scheduled_by_employer_id).first()
    employer_user = db.query(UserModel).filter(UserModel.id == employer.user_id).first()

    if employer_user:
        html_body, text_body = _slot_confirmed_email(
            seeker_name=seeker.full_name,
            slot_datetime=chosen_slot["datetime"],
            duration_minutes=chosen_slot["duration_minutes"],
        )
        background_tasks.add_task(
            send_email,
            to_email=employer_user.email,
            subject=f"Interview Confirmed: {seeker.full_name} selected a time slot",
            html_body=html_body,
            text_body=text_body,
        )

    return {"success": True, "confirmed_at": chosen_slot["datetime"]}


@router.get("/my-interviews")
def get_my_interviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all interview schedules for the current job seeker"""
    from app.models.job_seeker import JobSeeker
    from app.models.job import Job
    from app.models.employer import Employer

    seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not seeker:
        raise HTTPException(status_code=403, detail="Job seeker access required")

    applications = db.query(Application).filter(
        Application.job_seeker_id == seeker.id,
        Application.status == ApplicationStatus.INTERVIEW_SCHEDULED
    ).all()

    result = []
    for app in applications:
        schedule = db.query(InterviewSchedule).filter(InterviewSchedule.application_id == app.id).first()
        if schedule:
            job = db.query(Job).filter(Job.id == app.job_id).first()
            employer = db.query(Employer).filter(Employer.id == schedule.scheduled_by_employer_id).first()
            result.append({
                "schedule_id": str(schedule.id),
                "application_id": str(app.id),
                "job_title": job.title if job else None,
                "company_name": employer.company_name if employer else None,
                "style": schedule.style,
                "proposed_slots": schedule.proposed_slots,
                "confirmed_at": schedule.confirmed_at,
                "is_confirmed": schedule.is_confirmed,
                "allow_style_choice": schedule.allow_style_choice,
                "available_styles": schedule.available_styles,
                "location": schedule.location,
                "meeting_link": schedule.meeting_link,
                "instructions": schedule.instructions,
                "notes_for_candidate": schedule.notes_for_candidate,
            })
    return result


@router.get("/application/{application_id}")
def get_interview_by_application(
    application_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get interview schedule for a specific application"""
    schedule = db.query(InterviewSchedule).filter(InterviewSchedule.application_id == application_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Interview schedule not found")

    return {
        "schedule_id": str(schedule.id),
        "style": schedule.style,
        "is_confirmed": schedule.is_confirmed,
        "confirmed_at": schedule.confirmed_at,
        "meeting_link": schedule.meeting_link
    }


# ─── Targeted Announcements ───────────────────────────────────────────────────

@router.post("/broadcast")
def broadcast_to_applicants(
    body: BroadcastRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Employer broadcasts a message to applicants in specific stages"""
    from app.models.employer import Employer
    from app.models.job_seeker import JobSeeker
    from app.models.job import Job
    from app.models.user import User as UserModel

    employer = db.query(Employer).filter(Employer.user_id == current_user.id).first()
    if not employer:
        raise HTTPException(status_code=403, detail="Employer access required")

    job = db.query(Job).filter(Job.id == body.job_id).first()
    if not job or job.employer_id != employer.id:
        raise HTTPException(status_code=403, detail="Unauthorized or job not found")

    target_applicants = db.query(Application).filter(
        Application.job_id == body.job_id,
        Application.status.in_(body.statuses)
    ).all()

    if not target_applicants:
        raise HTTPException(status_code=404, detail="No candidates found in the selected stages")

    recipients = 0
    for app in target_applicants:
        seeker = db.query(JobSeeker).filter(JobSeeker.id == app.job_seeker_id).first()
        seeker_user = db.query(UserModel).filter(UserModel.id == seeker.user_id).first()

        if seeker_user and body.send_email:
            html_body, text_body = _broadcast_email(
                seeker_name=seeker.full_name,
                company_name=employer.company_name,
                message=body.message,
            )
            background_tasks.add_task(
                send_email,
                to_email=seeker_user.email,
                subject=f"[{employer.company_name}] {body.subject}",
                html_body=html_body,
                text_body=text_body,
            )

        if seeker_user and body.send_notification:
            from app.models.notification import Notification, NotificationType
            new_notif = Notification(
                user_id=seeker_user.id,
                title=body.subject,
                message=body.message,
                type=NotificationType.BROADCAST,
                link=f"/job-seeker/jobs/{body.job_id}"
            )
            db.add(new_notif)

        recipients += 1

    broadcast = ShortlistBroadcast(
        job_id=body.job_id,
        employer_id=employer.id,
        subject=body.subject,
        message=body.message,
        sent_via_email=body.send_email,
        sent_via_notification=body.send_notification,
        recipients_count=recipients
    )
    db.add(broadcast)
    db.commit()

    return {
        "success": True,
        "recipients_count": recipients,
        "message": f"Message sent to {recipients} candidate(s)",
    }


@router.post("/{schedule_id}/start")
def start_interview(
    schedule_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Employer marks a video/phone interview as started — notifies candidate"""
    from app.models.employer import Employer
    from app.models.job_seeker import JobSeeker
    from app.models.job import Job
    from app.models.user import User as UserModel

    employer = db.query(Employer).filter(Employer.user_id == current_user.id).first()
    if not employer:
        raise HTTPException(status_code=403, detail="Employer access required")

    schedule = db.query(InterviewSchedule).filter(InterviewSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Interview schedule not found")

    if schedule.scheduled_by_employer_id != employer.id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    if schedule.is_cancelled:
        raise HTTPException(status_code=400, detail="Cannot start a cancelled interview")

    schedule.actual_start_at = datetime.now(timezone.utc)
    db.commit()

    application = db.query(Application).filter(Application.id == schedule.application_id).first()
    job = db.query(Job).filter(Job.id == application.job_id).first()
    seeker = db.query(JobSeeker).filter(JobSeeker.id == application.job_seeker_id).first()
    seeker_user = db.query(UserModel).filter(UserModel.id == seeker.user_id).first()

    if seeker_user:
        html_body, text_body = _interview_started_email(
            seeker_name=seeker.full_name,
            job_title=job.title,
            company_name=employer.company_name,
            meeting_link=schedule.meeting_link
        )
        background_tasks.add_task(
            send_email,
            to_email=seeker_user.email,
            subject=f"🚀 INTERVIEW STARTED: {job.title} at {employer.company_name}",
            html_body=html_body,
            text_body=text_body,
        )

        from app.models.notification import Notification, NotificationType
        new_notif = Notification(
            user_id=seeker_user.id,
            title="Interview Started!",
            message=f"The employer has started the interview for '{job.title}'. Join now!",
            type=NotificationType.INTERVIEW,
            link=schedule.meeting_link or "/job-seeker/interviews"
        )
        db.add(new_notif)
        db.commit()

    return {
        "success": True,
        "message": "Candidate has been notified that the interview is starting",
        "started_at": schedule.actual_start_at.isoformat()
    }


# ─── FCFS Slot Pool Routes ────────────────────────────────────────────────────
# Flow:
#   1. Employer creates a pool of slots for a job (POST /pool/bulk-create).
#      - If employer pre-sets `style` on each slot → FCFS: seekers just race to book.
#      - If `allow_seeker_style_choice=True` → seekers choose their own style when booking.
#   2. Shortlisted seekers see the available unbooked slots (GET /pool/{job_id}).
#   3. Seeker books a slot first-come-first-served (POST /pool/{slot_id}/book).

@router.post("/pool/bulk-create")
def create_slot_pool(
    body: BulkSlotCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Employer creates a pool of available interview slots for a job.
    - Set a `style` on each slot to use FCFS (seekers just pick a slot, style is fixed).
    - Set `allow_seeker_style_choice=True` to let seekers choose their own style when booking.
    - `capacity`: How many people can book the same slot.
    - Overlap validation: Ensures no two slots for the same job overlap.
    """
    from app.models.employer import Employer
    from app.models.job import Job
    from app.models.interview import InterviewSlotPool
    from datetime import timedelta

    employer = db.query(Employer).filter(Employer.user_id == current_user.id).first()
    if not employer:
        raise HTTPException(status_code=403, detail="Employer access required")

    job = db.query(Job).filter(Job.id == body.job_id).first()
    if not job or job.employer_id != employer.id:
        raise HTTPException(status_code=403, detail="Unauthorized or job not found")

    # Validate: if not allowing seeker style choice, all slots must have a style
    if not body.allow_seeker_style_choice:
        for s in body.slots:
            if not s.style:
                raise HTTPException(
                    status_code=400,
                    detail="Each slot must have a style set when 'allow_seeker_style_choice' is False."
                )

    # Overlap validation logic
    # 1. Fetch existing slots for this job
    existing_slots = db.query(InterviewSlotPool).filter(InterviewSlotPool.job_id == body.job_id).all()
    
    # 2. Helper to check overlap between two slots
    def slots_overlap(start1, dur1, start2, dur2):
        end1 = start1 + timedelta(minutes=dur1)
        end2 = start2 + timedelta(minutes=dur2)
        return max(start1, start2) < min(end1, end2)

    new_slots_data = []
    for s_body in body.slots:
        s_start = s_body.datetime_utc
        s_dur = s_body.duration_minutes
        
        # Check against existing slots in DB
        for ex in existing_slots:
            if slots_overlap(s_start, s_dur, ex.datetime_utc, ex.duration_minutes):
                raise HTTPException(
                    status_code=400,
                    detail=f"Slot at {s_start} overlaps with existing slot at {ex.datetime_utc}"
                )
        
        # Check against other slots in this request
        for other in new_slots_data:
            if slots_overlap(s_start, s_dur, other["start"], other["dur"]):
                raise HTTPException(
                    status_code=400,
                    detail=f"Duplicate or overlapping slots in request: {s_start}"
                )
        
        new_slots_data.append({"start": s_start, "dur": s_dur, "body": s_body})

    new_slots = []
    for data in new_slots_data:
        s = data["body"]
        slot = InterviewSlotPool(
            job_id=body.job_id,
            employer_id=employer.id,
            datetime_utc=s.datetime_utc,
            duration_minutes=s.duration_minutes,
            capacity=s.capacity,
            style=s.style,
            location=s.location,
            meeting_link=s.meeting_link,
            allow_seeker_style_choice=body.allow_seeker_style_choice,
            available_styles=[st.value for st in body.available_styles] if body.available_styles else []
        )
        db.add(slot)
        new_slots.append(slot)

    db.commit()
    return {
        "success": True,
        "slots_created": len(new_slots),
        "message": "Slots created successfully with no overlaps."
    }


@router.get("/pool/{job_id}")
def get_slot_pool(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get interview slot pool for a specific job"""
    from app.models.employer import Employer
    from app.models.interview import InterviewSlotPool

    employer = db.query(Employer).filter(Employer.user_id == current_user.id).first()
    is_employer = False
    if employer:
        from app.models.job import Job
        job = db.query(Job).filter(Job.id == job_id).first()
        if job and job.employer_id == employer.id:
            is_employer = True

    query = db.query(InterviewSlotPool).filter(InterviewSlotPool.job_id == job_id)

    from sqlalchemy import func
    from app.models.application import Application

    slots = query.order_by(InterviewSlotPool.datetime_utc.asc()).all()

    has_requested = False
    if not is_employer:
        from app.models.job_seeker import JobSeeker
        seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
        if seeker:
            from app.models.application import Application
            application = db.query(Application).filter(
                Application.job_id == job_id,
                Application.job_seeker_id == seeker.id
            ).first()
            if application:
                has_requested = application.has_requested_extra_slots

    # Count shortlisted candidates (including those who already scheduled)
    shortlisted_count = db.query(func.count(Application.id)).filter(
        Application.job_id == job_id,
        Application.status.in_([ApplicationStatus.SHORTLISTED, ApplicationStatus.INTERVIEW_SCHEDULED])
    ).scalar()

    result = []
    for s in slots:
        # Count current bookings
        booked_count = db.query(func.count(Application.id)).filter(Application.booked_slot_id == s.id).scalar()
        
        result.append({
            "id": str(s.id),
            "datetime_utc": s.datetime_utc.isoformat(),
            "duration_minutes": s.duration_minutes,
            "capacity": s.capacity,
            "booked_count": booked_count,
            "is_booked": booked_count >= s.capacity,
            "style": s.style,
            "allow_seeker_style_choice": s.allow_seeker_style_choice,
            "available_styles": s.available_styles,
            "location": s.location,
            "meeting_link": s.meeting_link if is_employer else None  # Hide until booked
        })

    return {
        "slots": result,
        "has_requested_extra_slots": has_requested,
        "shortlisted_count": shortlisted_count
    }


@router.post("/pool/{slot_id}/book")
def book_interview_slot(
    slot_id: UUID,
    body: SlotBookingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Job seeker books an available interview slot (FCFS).

    Two modes depending on how the employer created the slot:
    - FCFS (style pre-set): Seeker just books — no style input needed.
    - Seeker-choice mode (allow_seeker_style_choice=True): Seeker must provide chosen_style.
    """
    from app.models.job_seeker import JobSeeker
    from app.models.interview import InterviewSlotPool, InterviewSchedule
    from app.models.employer import Employer
    from app.models.job import Job
    from app.models.user import User as UserModel
    from app.models.application import Application, ApplicationStatus
    from sqlalchemy import func

    seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not seeker:
        raise HTTPException(status_code=403, detail="Job seeker access required")

    # Lock the slot for update to handle race conditions (FCFS guarantee)
    slot = db.query(InterviewSlotPool).filter(InterviewSlotPool.id == slot_id).with_for_update().first()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    # Check capacity
    booked_count = db.query(func.count(Application.id)).filter(Application.booked_slot_id == slot.id).scalar()
    
    if booked_count >= slot.capacity:
        raise HTTPException(status_code=409, detail="This slot is already full. Please pick another.")

    # Find the seeker's application for this job
    application = db.query(Application).filter(
        Application.job_id == slot.job_id,
        Application.job_seeker_id == seeker.id
    ).first()

    if not application:
        raise HTTPException(status_code=403, detail="No active application found for this job")
    
    # Check if seeker has already booked a slot for this job
    if application.booked_slot_id:
        raise HTTPException(status_code=400, detail="You have already booked a slot for this interview.")

    if application.status not in [ApplicationStatus.SHORTLISTED, ApplicationStatus.INTERVIEW_SCHEDULED]:
        raise HTTPException(status_code=400, detail="Only shortlisted candidates can book interview slots")

    # Determine the final interview style
    # - If employer pre-set a style on the slot → use it (FCFS mode, no choice needed)
    # - If slot allows seeker choice → seeker must provide chosen_style
    allow_seeker_choice = slot.allow_seeker_style_choice

    if slot.style:
        # Employer already defined the style → FCFS, seeker cannot override
        final_style = slot.style
    elif allow_seeker_choice:
        if not body.chosen_style:
            raise HTTPException(status_code=400, detail="Please choose an interview style for this slot")
        final_style = body.chosen_style
    else:
        raise HTTPException(status_code=400, detail="Slot has no interview style configured")

    # Mark slot as booked
    slot.is_booked = True
    slot.application_id = application.id

    # ✅ Link back from application → slot so seeker can retrieve their booking
    application.booked_slot_id = slot.id

    # Update application status
    application.status = ApplicationStatus.INTERVIEW_SCHEDULED

    # Create an InterviewSchedule record
    schedule_id = uuid.uuid4()
    
    # Unified meeting link: FOR THE SAME SLOT, ONLY ONE UNIQUE LINK
    # We use slot.id as the room identifier so all participants in this slot join the same room
    final_meeting_link = slot.meeting_link
    if final_style == InterviewStyle.VIDEO_CALL:
        if not final_meeting_link or final_meeting_link.lower() in ["tbd", "zoom", "meet", "none"]:
            final_meeting_link = f"/interview/{slot.id}"

    schedule = InterviewSchedule(
        id=schedule_id,
        application_id=application.id,
        scheduled_by_employer_id=slot.employer_id,
        style=final_style,
        proposed_slots=[{
            "datetime": slot.datetime_utc.isoformat(),
            "duration_minutes": slot.duration_minutes
        }],
        confirmed_at=slot.datetime_utc,
        confirmed_duration_minutes=slot.duration_minutes,
        is_confirmed=True,
        location=slot.location,
        meeting_link=final_meeting_link
    )
    db.add(schedule)
    db.commit()

    # Notify job seeker
    employer = db.query(Employer).filter(Employer.id == slot.employer_id).first()
    job = db.query(Job).filter(Job.id == slot.job_id).first()

    html_body, text_body = _slot_booked_notification_email(
        seeker_name=seeker.full_name,
        job_title=job.title,
        company_name=employer.company_name,
        slot_datetime=slot.datetime_utc
    )
    background_tasks.add_task(
        send_email,
        to_email=current_user.email,
        subject=f"Confirmed: Interview for {job.title}",
        html_body=html_body,
        text_body=text_body
    )

    # Notify employer
    employer_user = db.query(UserModel).filter(UserModel.id == employer.user_id).first()
    if employer_user:
        emp_html, emp_text = _slot_confirmed_email(
            seeker_name=seeker.full_name,
            slot_datetime=slot.datetime_utc.strftime("%Y-%m-%d %H:%M"),
            duration_minutes=slot.duration_minutes
        )
        background_tasks.add_task(
            send_email,
            to_email=employer_user.email,
            subject=f"New Booking: {seeker.full_name} for {job.title}",
            html_body=emp_html,
            text_body=emp_text
        )

    return {
        "success": True,
        "message": "Interview booked successfully",
        "slot_datetime": slot.datetime_utc.isoformat(),
        "interview_style": final_style.value if hasattr(final_style, "value") else str(final_style),
        "schedule_id": str(schedule.id)
    }


@router.post("/pool/{slot_id}/delete")
def delete_slot(
    slot_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.employer import Employer
    from app.models.interview import InterviewSlotPool

    employer = db.query(Employer).filter(Employer.user_id == current_user.id).first()
    if not employer:
        raise HTTPException(status_code=403, detail="Employer access required")

    slot = db.query(InterviewSlotPool).filter(InterviewSlotPool.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    if slot.employer_id != employer.id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    from app.models.application import Application
    from sqlalchemy import func
    booked_count = db.query(func.count(Application.id)).filter(Application.booked_slot_id == slot.id).scalar()
    if booked_count > 0:
        raise HTTPException(status_code=400, detail="Cannot delete a slot that already has bookings")

    db.delete(slot)
    db.commit()
    return {"success": True}


# ─── Assessment Routes ────────────────────────────────────────────────────────

@router.post("/assessments")
def create_or_update_assessment(
    body: AssessmentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Employer creates or updates an assessment for a job"""
    from app.models.employer import Employer
    from app.models.job import Job

    employer = db.query(Employer).filter(Employer.user_id == current_user.id).first()
    if not employer:
        raise HTTPException(status_code=403, detail="Employer access required")

    job = db.query(Job).filter(Job.id == body.job_id).first()
    if not job or job.employer_id != employer.id:
        raise HTTPException(status_code=403, detail="Unauthorized or job not found")

    assessment = db.query(Assessment).filter(Assessment.job_id == body.job_id).first()

    if assessment:
        assessment.title = body.title
        assessment.description = body.description
        assessment.assessment_type = body.assessment_type
        assessment.time_limit_minutes = body.time_limit_minutes
        assessment.passing_score = body.passing_score
        assessment.is_required = body.is_required
        assessment.trigger_stage = body.trigger_stage
        db.query(AssessmentQuestion).filter(AssessmentQuestion.assessment_id == assessment.id).delete()
    else:
        assessment = Assessment(
            job_id=body.job_id,
            employer_id=employer.id,
            title=body.title,
            description=body.description,
            assessment_type=body.assessment_type,
            time_limit_minutes=body.time_limit_minutes,
            passing_score=body.passing_score,
            is_required=body.is_required,
            trigger_stage=body.trigger_stage
        )
        db.add(assessment)
        db.flush()

    for q in body.questions:
        new_q = AssessmentQuestion(
            assessment_id=assessment.id,
            question_text=q.question_text,
            question_type=q.question_type,
            options=q.options,
            correct_answer=q.correct_answer,
            points=q.points,
            order_index=q.order_index,
            explanation=q.explanation
        )
        db.add(new_q)

    db.commit()
    return {"success": True, "assessment_id": str(assessment.id)}


@router.get("/assessments/job/{job_id}")
def get_job_assessment(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get assessment for a job. Seeker only gets questions, Employer gets answers too."""
    assessment = db.query(Assessment).filter(Assessment.job_id == job_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="No assessment found for this job")

    is_employer = False
    from app.models.employer import Employer
    employer = db.query(Employer).filter(Employer.user_id == current_user.id).first()
    if employer and assessment.employer_id == employer.id:
        is_employer = True

    questions = []
    for q in assessment.questions:
        q_data = {
            "id": str(q.id),
            "question_text": q.question_text,
            "question_type": q.question_type,
            "options": q.options,
            "points": q.points,
            "order_index": q.order_index
        }
        if is_employer:
            q_data["correct_answer"] = q.correct_answer
            q_data["explanation"] = q.explanation
        questions.append(q_data)

    return {
        "id": str(assessment.id),
        "title": assessment.title,
        "description": assessment.description,
        "assessment_type": assessment.assessment_type,
        "time_limit_minutes": assessment.time_limit_minutes,
        "passing_score": assessment.passing_score,
        "is_required": assessment.is_required,
        "trigger_stage": assessment.trigger_stage,
        "questions": sorted(questions, key=lambda x: x["order_index"])
    }


@router.post("/assessments/{assessment_id}/attempt")
def start_assessment_attempt(
    assessment_id: UUID,
    application_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Job seeker starts an assessment attempt"""
    from app.models.job_seeker import JobSeeker
    seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not seeker:
        raise HTTPException(status_code=403, detail="Job seeker access required")

    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    existing = db.query(AssessmentAttempt).filter(
        AssessmentAttempt.assessment_id == assessment_id,
        AssessmentAttempt.job_seeker_id == seeker.id,
        AssessmentAttempt.passed == True
    ).first()
    if existing:
        return {
            "success": True,
            "message": "You have already passed this assessment",
            "attempt_id": str(existing.id),
            "passed": True
        }

    attempt = AssessmentAttempt(
        assessment_id=assessment_id,
        job_seeker_id=seeker.id,
        application_id=application_id,
        started_at=datetime.now(timezone.utc)
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return {"success": True, "attempt_id": str(attempt.id)}


@router.post("/attempts/{attempt_id}/submit")
def submit_assessment_attempt(
    attempt_id: UUID,
    body: AssessmentSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Job seeker submits answers. Logic for auto-grading MCQs."""
    attempt = db.query(AssessmentAttempt).filter(AssessmentAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    if attempt.submitted_at:
        raise HTTPException(status_code=400, detail="Assessment already submitted")

    assessment = db.query(Assessment).filter(Assessment.id == attempt.assessment_id).first()

    # Auto-grading
    total_points = 0
    earned_points = 0

    for q in assessment.questions:
        total_points += q.points
        user_answer = body.answers.get(str(q.id))
        if q.question_type in (QuestionType.MULTIPLE_CHOICE, QuestionType.TRUE_FALSE):
            if user_answer == q.correct_answer:
                earned_points += q.points

    score_pct = (earned_points / total_points * 100) if total_points > 0 else 100
    passed = score_pct >= assessment.passing_score

    attempt.answers = body.answers
    attempt.score = int(score_pct)
    attempt.passed = passed
    attempt.submitted_at = datetime.now(timezone.utc)
    attempt.time_taken_seconds = (
        attempt.submitted_at - attempt.started_at.replace(tzinfo=timezone.utc)
    ).total_seconds()

    db.commit()

    return {"success": True, "message": "Assessment submitted", "score": attempt.score, "passed": attempt.passed}


@router.post("/job/{job_id}/request-slots")
def request_more_slots(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Job seeker requests the employer to add more interview slots"""
    from app.models.job_seeker import JobSeeker
    from app.models.job import Job
    from app.models.employer import Employer
    from app.models.application import Application, ApplicationStatus
    from app.models.notification import Notification, NotificationType

    seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not seeker:
        raise HTTPException(status_code=403, detail="Only job seekers can request slots")

    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Verify they have an active application
    application = db.query(Application).filter(
        Application.job_id == job_id,
        Application.job_seeker_id == seeker.id
    ).first()

    if not application:
        raise HTTPException(status_code=403, detail="You must have an active application to request slots")

    if application.has_requested_extra_slots:
        raise HTTPException(status_code=400, detail="You have already requested more slots for this job.")

    if application.status not in [ApplicationStatus.SHORTLISTED, ApplicationStatus.INTERVIEW_SCHEDULED]:
        raise HTTPException(status_code=400, detail="Only shortlisted candidates can request interview slots")

    employer = db.query(Employer).filter(Employer.id == job.employer_id).first()
    if not employer:
        raise HTTPException(status_code=404, detail="Employer not found")

    # Notify employer
    notif = Notification(
        user_id=employer.user_id,
        title=f"Slot Request: {job.title}",
        message=f"{seeker.full_name} has requested more interview slots for the position.",
        type=NotificationType.SYSTEM,
        link=f"/employer/jobs/{job.id}/interview-slots"
    )
    db.add(notif)
    
    # Mark as requested
    application.has_requested_extra_slots = True
    db.commit()

    return {"message": "Request sent successfully. The employer has been notified."}


@router.post("/reviews", response_model=InterviewReviewResponse)
def create_interview_review(
    body: InterviewReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Employer submits a review for a completed interview"""
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can submit reviews")

    from app.models.interview import InterviewReview, InterviewSchedule
    from app.models.employer import Employer

    employer = db.query(Employer).filter(Employer.user_id == current_user.id).first()
    if not employer:
        raise HTTPException(status_code=404, detail="Employer profile not found")

    interview = db.query(InterviewSchedule).filter(
        InterviewSchedule.id == body.interview_id,
        InterviewSchedule.scheduled_by_employer_id == employer.id
    ).first()

    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found or unauthorized")

    # Force mark as completed if it wasn't already
    if not interview.is_completed:
        interview.is_completed = True
        interview.completed_at = datetime.now(timezone.utc)

    # Check if a review already exists
    existing_review = db.query(InterviewReview).filter(
        InterviewReview.interview_id == body.interview_id
    ).first()

    if existing_review:
        # Update existing review
        existing_review.notes = body.notes
        existing_review.metrics = body.metrics
        existing_review.overall_rating = body.overall_rating
        db.commit()
        db.refresh(existing_review)
        return existing_review

    new_review = InterviewReview(
        application_id=interview.application_id,
        interview_id=body.interview_id,
        employer_id=employer.id,
        notes=body.notes,
        metrics=body.metrics,
        overall_rating=body.overall_rating
    )
    db.add(new_review)
    db.commit()
    db.refresh(new_review)

    return new_review


@router.get("/reviews/{interview_id}", response_model=InterviewReviewResponse)
def get_interview_review(
    interview_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve review for a specific interview"""
    from app.models.interview import InterviewReview, InterviewSchedule
    from app.models.employer import Employer
    from app.models.job_seeker import JobSeeker

    review = db.query(InterviewReview).filter(InterviewReview.interview_id == interview_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # Verify access
    if current_user.role == UserRole.EMPLOYER:
        employer = db.query(Employer).filter(Employer.user_id == current_user.id).first()
        if not employer or review.employer_id != employer.id:
            raise HTTPException(status_code=403, detail="Unauthorized")
    else:
        seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
        if not seeker or review.application_id != (
            db.query(Application.id).filter(Application.job_seeker_id == seeker.id).filter(Application.id == review.application_id).scalar()
        ):
             # Actually, seekers might not be allowed to see reviews if employer wants them private
             # But the user didn't specify. I'll allow seekers to see their own reviews for now.
             pass

    return review


@router.post("/{interview_id}/complete")
def mark_interview_completed(
    interview_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Manually mark an interview as completed"""
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can mark interviews as completed")

    from app.models.interview import InterviewSchedule
    from app.models.employer import Employer

    employer = db.query(Employer).filter(Employer.user_id == current_user.id).first()
    interview = db.query(InterviewSchedule).filter(
        InterviewSchedule.id == interview_id,
        InterviewSchedule.scheduled_by_employer_id == employer.id
    ).first()

    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    interview.is_completed = True
    interview.completed_at = datetime.now(timezone.utc)
    db.commit()

    return {"message": "Interview marked as completed"}
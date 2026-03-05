# app/routes/interview_routes.py
"""
Enhanced interview scheduling and shortlist broadcast routes.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone

from app.database import get_db
from app.utils.security import get_current_user
from app.models.interview import InterviewSchedule, InterviewStyle, ShortlistBroadcast, Assessment, AssessmentQuestion, AssessmentAttempt, QuestionType
from app.models.application import Application, ApplicationStatus
from app.models.user import User, UserRole
from app.utils.email import send_email


router = APIRouter(prefix="/interviews", tags=["interviews"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

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
    send_email: bool = True
    send_notification: bool = True


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
    # Convert newlines to <br> for HTML
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

    # Email job seeker
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

    db.commit()

    # Email employer
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


# ─── Shortlist Broadcast ──────────────────────────────────────────────────────

@router.post("/broadcast")
def broadcast_to_shortlisted(
    body: BroadcastRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Employer broadcasts a message to all shortlisted candidates for a job"""
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

    shortlisted = db.query(Application).filter(
        Application.job_id == body.job_id,
        Application.status == ApplicationStatus.SHORTLISTED
    ).all()

    if not shortlisted:
        raise HTTPException(status_code=404, detail="No shortlisted candidates found")

    recipients = 0
    for app in shortlisted:
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
        "message": f"Message sent to {recipients} shortlisted candidate(s)",
    }
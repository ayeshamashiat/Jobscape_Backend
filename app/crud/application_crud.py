# app/crud/application_crud.py
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from app.models.application import Application, ApplicationStatus
from app.models.job import Job
from app.models.job_seeker import JobSeeker
from app.models.employer import Employer
from app.utils.ats_scorer import score_resume_against_job
from app.models.resume import Resume
from typing import List, Optional
import uuid
from datetime import datetime, timezone


def calculate_match_score(job: Job, job_seeker: JobSeeker) -> tuple[int, dict]:
    """Calculate how well job seeker matches job requirements"""
    required_skills = set(job.required_skills)
    preferred_skills = set(job.preferred_skills)
    applicant_skills = set(job_seeker.skills)
    
    matched_required = required_skills & applicant_skills
    matched_preferred = preferred_skills & applicant_skills
    missing_required = required_skills - applicant_skills
    
    # Calculate score
    required_weight = 70
    preferred_weight = 30
    
    required_score = (len(matched_required) / len(required_skills) * required_weight) if required_skills else required_weight
    preferred_score = (len(matched_preferred) / len(preferred_skills) * preferred_weight) if preferred_skills else preferred_weight
    
    total_score = int(required_score + preferred_score)
    
    skills_match = {
        "matched_required": list(matched_required),
        "matched_preferred": list(matched_preferred),
        "missing_required": list(missing_required),
        "total_required": len(required_skills),
        "total_preferred": len(preferred_skills)
    }
    
    return total_score, skills_match


def create_application(
    db: Session,
    job_id: uuid.UUID,
    job_seeker_id: uuid.UUID,
    resume_id: uuid.UUID,
    cover_letter: Optional[str] = None
) -> Application:
    """Create new application"""
    
    # Check if already applied
    existing = db.query(Application).filter(
        and_(
            Application.job_id == job_id,
            Application.job_seeker_id == job_seeker_id
        )
    ).first()
    
    if existing:
        raise ValueError("You have already applied to this job")
    
    # Get job and job seeker for match calculation
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise ValueError("Job not found")
    
    if not job.is_active or job.is_closed:
        raise ValueError("This job is no longer accepting applications")
    
    # Check if deadline passed
    if job.application_deadline and datetime.now(timezone.utc) > job.application_deadline:
        raise ValueError("Application deadline has passed")
    
    job_seeker = db.query(JobSeeker).filter(JobSeeker.id == job_seeker_id).first()
    if not job_seeker:
        raise ValueError("Job seeker profile not found")
    
    # Calculate match score
    match_score, skills_match = calculate_match_score(job, job_seeker)
    
    application = Application(
        job_id=job_id,
        job_seeker_id=job_seeker_id,
        resume_id=resume_id,
        cover_letter=cover_letter,
        status=ApplicationStatus.PENDING,
        match_score=match_score,
        skills_match=skills_match,
        current_round=0
    )
    
    db.add(application)
    db.commit()
    db.refresh(application)
    
    # 🔔 Send In-App Notification to Employer
    try:
        from app.models.notification import Notification, NotificationType
        from app.models.employer import Employer
        
        # Get employer user_id
        employer_user_id = db.query(Employer.user_id).filter(Employer.id == job.employer_id).scalar()
        
        if employer_user_id:
            new_notif = Notification(
                user_id=employer_user_id,
                title="New Application Received",
                message=f"{job_seeker.full_name} has applied for '{job.title}'.",
                type=NotificationType.APPLICATION,
                link=f"/employer/jobs"
            )
            db.add(new_notif)
            db.commit()
    except Exception as e:
        print(f"Failed to trigger employer application notification: {e}")
    
    return application


def get_application_by_id(db: Session, application_id: uuid.UUID) -> Optional[Application]:
    """Get application by ID"""
    return db.query(Application).filter(Application.id == application_id).first()


def get_job_seeker_applications(
    db: Session,
    job_seeker_id: uuid.UUID,
    status: Optional[ApplicationStatus] = None,
    skip: int = 0,
    limit: int = 20
) -> List[Application]:
    """Get all applications by job seeker"""
    query = db.query(Application).filter(Application.job_seeker_id == job_seeker_id)
    
    if status:
        query = query.filter(Application.status == status)
    
    return query.order_by(Application.applied_at.desc()).offset(skip).limit(limit).all()


def get_job_applications(
    db: Session,
    job_id: uuid.UUID,
    status: Optional[ApplicationStatus] = None,
    min_match_score: Optional[int] = None,
    min_ats_score: Optional[int] = None,
    skip: int = 0,
    limit: int = 50
) -> List[Application]:
    """Get all applications for a job (employer view)"""
    query = db.query(Application).filter(Application.job_id == job_id)
    
    if status:
        query = query.filter(Application.status == status)
    
    if min_match_score:
        query = query.filter(Application.match_score >= min_match_score)

    if min_ats_score:
        query = query.filter(Application.ats_score >= min_ats_score)
    
    return query.order_by(Application.match_score.desc(), Application.applied_at.desc()).offset(skip).limit(limit).all()


def get_employer_applications(
    db: Session,
    employer_id: uuid.UUID,
    status: Optional[ApplicationStatus] = None,
    skip: int = 0,
    limit: int = 50
) -> List[Application]:
    """Get all applications for employer's jobs"""
    query = db.query(Application).join(Job).filter(Job.employer_id == employer_id)
    
    if status:
        query = query.filter(Application.status == status)
    
    return query.order_by(Application.applied_at.desc()).offset(skip).limit(limit).all()


def update_application_status(
    db: Session,
    application_id: uuid.UUID,
    employer_id: uuid.UUID,
    status: ApplicationStatus,
    employer_notes: Optional[str] = None,
    rejection_reason: Optional[str] = None,
    interview_scheduled_at: Optional[datetime] = None,
    interview_location: Optional[str] = None,
    interview_notes: Optional[str] = None
) -> Application:
    """Employer updates application status"""
    
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise ValueError("Application not found")
    
    # Verify employer owns this job
    job = db.query(Job).filter(Job.id == application.job_id).first()
    if job.employer_id != employer_id:
        raise ValueError("Unauthorized")
    
    application.status = status
    
    if employer_notes:
        application.employer_notes = employer_notes
    
    if status == ApplicationStatus.REJECTED:
        application.rejection_reason = rejection_reason
        application.rejected_at = datetime.now(timezone.utc)
    
    if status == ApplicationStatus.INTERVIEW_SCHEDULED:
        application.interview_scheduled_at = interview_scheduled_at
        application.interview_location = interview_location
        application.interview_notes = interview_notes
    
    db.commit()
    db.refresh(application)

    # 🔔 Send In-App Notification
    try:
        from app.models.notification import Notification, NotificationType
        
        seeker_user_id = db.query(JobSeeker.user_id).filter(JobSeeker.id == application.job_seeker_id).scalar()
        
        status_messages = {
            ApplicationStatus.REVIEWED: f"Your application for '{job.title}' has been reviewed.",
            ApplicationStatus.SHORTLISTED: f"Congratulations! You've been shortlisted for '{job.title}'.",
            ApplicationStatus.INTERVIEW_SCHEDULED: f"An interview has been scheduled for '{job.title}'.",
            ApplicationStatus.ACCEPTED: f"Congratulations! You've been selected for the position of '{job.title}'.",
            ApplicationStatus.REJECTED: f"Status update regarding your application for '{job.title}'.",
        }
        
        if seeker_user_id and status in status_messages:
            new_notif = Notification(
                user_id=seeker_user_id,
                title=f"Application Update: {status.value.replace('_', ' ').title()}",
                message=status_messages[status],
                type=NotificationType.APPLICATION,
                link=f"/job-seeker/applications"
            )
            db.add(new_notif)
            db.commit()
    except Exception as e:
        print(f"Failed to trigger in-app notification: {e}")
    
    return application


def withdraw_application(db: Session, application_id: uuid.UUID, job_seeker_id: uuid.UUID) -> Application:
    """Job seeker withdraws application"""
    
    application = db.query(Application).filter(
        and_(
            Application.id == application_id,
            Application.job_seeker_id == job_seeker_id
        )
    ).first()
    
    if not application:
        raise ValueError("Application not found")
    
    if application.status in [ApplicationStatus.ACCEPTED, ApplicationStatus.REJECTED]:
        raise ValueError("Cannot withdraw application with this status")
    
    application.status = ApplicationStatus.WITHDRAWN
    db.commit()
    db.refresh(application)
    
    return application


def get_application_stats(db: Session, job_id: uuid.UUID) -> dict:
    """Get application statistics for a job"""
    
    total = db.query(Application).filter(Application.job_id == job_id).count()
    pending = db.query(Application).filter(
        and_(Application.job_id == job_id, Application.status == ApplicationStatus.PENDING)
    ).count()
    reviewed = db.query(Application).filter(
        and_(Application.job_id == job_id, Application.status == ApplicationStatus.REVIEWED)
    ).count()
    shortlisted = db.query(Application).filter(
        and_(Application.job_id == job_id, Application.status == ApplicationStatus.SHORTLISTED)
    ).count()
    interview_scheduled = db.query(Application).filter(
        and_(Application.job_id == job_id, Application.status == ApplicationStatus.INTERVIEW_SCHEDULED)
    ).count()
    accepted = db.query(Application).filter(
        and_(Application.job_id == job_id, Application.status == ApplicationStatus.ACCEPTED)
    ).count()
    rejected = db.query(Application).filter(
        and_(Application.job_id == job_id, Application.status == ApplicationStatus.REJECTED)
    ).count()
    
    return {
        "total_applications": total,
        "pending": pending,
        "reviewed": reviewed,
        "shortlisted": shortlisted,
        "interview_scheduled": interview_scheduled,
        "accepted": accepted,
        "rejected": rejected
    }


def get_application_with_details(
    db: Session,
    application_id: uuid.UUID,
    employer_id: uuid.UUID
) -> Optional[Application]:
    """
    Get application with full details including resume (for employer)
    Verifies employer owns the job this application is for
    """
    from app.models.job import Job
    
    application = db.query(Application).filter(
        Application.id == application_id
    ).first()
    
    if not application:
        return None
    
    # Verify employer owns the job
    job = db.query(Job).filter(Job.id == application.job_id).first()
    if not job or job.employer_id != employer_id:
        return None
    
    return application


def get_application_resume(
    db: Session,
    application_id: uuid.UUID,
    employer_id: uuid.UUID
) -> Optional[dict]:
    """
    Get resume details for an application
    Returns None if application not found or employer doesn't own the job
    """
    application = get_application_with_details(db, application_id, employer_id)
    
    if not application or not application.resume_id:
        return None
    
    from app.models.resume import Resume
    resume = db.query(Resume).filter(Resume.id == application.resume_id).first()
    
    if not resume:
        return None
    
    return {
        "id": str(resume.id),
        "file_url": resume.file_url,
        "file_name": resume.file_name,
        "uploaded_at": resume.uploaded_at
    }


def get_application_full_details(
    db: Session,
    application_id: uuid.UUID,
    employer_id: uuid.UUID
) -> Optional[dict]:
    """
    Get complete application details including job seeker info and resume
    """
    application = get_application_with_details(db, application_id, employer_id)
    
    if not application:
        return None
    
    from app.models.job_seeker import JobSeeker
    from app.models.user import User
    from app.models.resume import Resume
    
    # Get job seeker
    job_seeker = db.query(JobSeeker).filter(
        JobSeeker.id == application.job_seeker_id
    ).first()
    
    if not job_seeker:
        return None
    
    # Get user
    user = db.query(User).filter(User.id == job_seeker.user_id).first()
    
    # Get resume
    resume = None
    if application.resume_id:
        resume = db.query(Resume).filter(Resume.id == application.resume_id).first()
    
    return {
        "application": application,
        "job_seeker": {
            "id": str(job_seeker.id),
            "full_name": job_seeker.full_name,
            "email": user.email if user else None,
            "phone": job_seeker.phone,
            "location": job_seeker.location,
            "summary": job_seeker.professional_summary,
            "skills": job_seeker.skills,
            "experience": job_seeker.experience,
            "education": job_seeker.education,
            "certifications": job_seeker.certifications,
            "languages": job_seeker.languages,
            "portfolio_links": job_seeker.portfolio_url,
        },
        "resume": {
            "id": str(resume.id),
            "file_url": resume.file_url,
            "uploaded_at": resume.uploaded_at,
            "parsed_data": resume.parsed_data
        } if resume else None
    }

async def score_application_ats(
    db: Session, application_id: uuid.UUID, employer_id: uuid.UUID
) -> Application:
    """Score a single application using AI ATS."""
    application = get_application_with_details(db, application_id, employer_id)
    if not application:
        raise ValueError("Application not found or unauthorized")

    job = db.query(Job).filter(Job.id == application.job_id).first()
    if not job:
        raise ValueError("Job not found")

    resume = db.query(Resume).filter(Resume.id == application.resume_id).first()
    if not resume or not resume.parsed_data:
        raise ValueError("Resume not parsed yet. Cannot score.")

    ats_result = score_resume_against_job(
        resume_parsed_data=resume.parsed_data,
        job_title=job.title,
        job_description=job.description,
        required_skills=job.required_skills or [],
        preferred_skills=job.preferred_skills or [],
        experience_level=job.experience_level,
    )

    application.ats_score = ats_result.get("overall_score", 0)
    application.ats_report = ats_result
    db.commit()
    db.refresh(application)

    # 🔔 Send In-App Notification
    try:
        from app.models.notification import Notification, NotificationType
        seeker_user_id = db.query(JobSeeker.user_id).filter(JobSeeker.id == application.job_seeker_id).scalar()
        
        if seeker_user_id:
            next_round_data = process.rounds[application.current_round - 1]
            new_notif = Notification(
                user_id=seeker_user_id,
                title=f"Next Round: {next_round_data.get('title', 'Interview scheduled')}",
                message=f"You've been moved to the next round of selection for '{job.title}' at {job.employer.company_name}.",
                type=NotificationType.INTERVIEW,
                link=f"/job-seeker/applications"
            )
            db.add(new_notif)
            db.commit()
    except Exception as e:
        print(f"Failed to trigger in-app notification: {e}")

    return application


def bulk_score_job_applications(
    db: Session, job_id: uuid.UUID, employer_id: uuid.UUID
) -> dict:
    """Score ALL applications for a job in bulk."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job or job.employer_id != employer_id:
        raise ValueError("Job not found or unauthorized")

    applications = db.query(Application).filter(Application.job_id == job_id).all()

    scored, failed, skipped = 0, 0, 0
    for app in applications:
        try:
            resume = db.query(Resume).filter(Resume.id == app.resume_id).first()
            if not resume or not resume.parsed_data:
                skipped += 1
                continue

            ats_result = score_resume_against_job(
                resume_parsed_data=resume.parsed_data,
                job_title=job.title,
                job_description=job.description,
                required_skills=job.required_skills or [],
                preferred_skills=job.preferred_skills or [],
                experience_level=job.experience_level,
            )
            app.ats_score = ats_result.get("overall_score", 0)
            app.ats_report = ats_result
            scored += 1
        except Exception as e:
            failed += 1
            print(f"Failed to score application {app.id}: {e}")

    db.commit()
    return {
        "total": len(applications),
        "scored": scored,
        "failed": failed,
        "skipped_no_resume": skipped,
    }


def advance_candidate_round(
    db: Session,
    application_id: uuid.UUID,
    employer_id: uuid.UUID,
    next_status: Optional[ApplicationStatus] = None
) -> Application:
    """Move a candidate to the next round in the selection process."""
    application = get_application_by_id(db, application_id)
    if not application:
        raise ValueError("Application not found")

    # Verify employer owns the job
    job = db.query(Job).filter(Job.id == application.job_id).first()
    if not job or job.employer_id != employer_id:
        raise ValueError("Unauthorized")

    from app.models.selection_round import SelectionProcess
    process = db.query(SelectionProcess).filter(SelectionProcess.job_id == application.job_id).first()
    
    if not process or not process.rounds:
         raise ValueError("No selection process defined for this job")

    current_round = application.current_round
    total_rounds = len(process.rounds)

    if current_round >= total_rounds:
        # Already finished all rounds, move to next status (e.g., ACCEPTED/REJECTED)
        if next_status:
             application.status = next_status
    else:
        # Move to next round
        application.current_round += 1
        application.status = ApplicationStatus.INTERVIEW_SCHEDULED
        
        # Notify candidate
        try:
            from app.utils.email import send_round_advancement_email
            from app.models.user import User as UserModel
            
            job_seeker = db.query(JobSeeker).filter(JobSeeker.id == application.job_seeker_id).first()
            user = db.query(UserModel).filter(UserModel.id == job_seeker.user_id).first()
            
            next_round_data = process.rounds[application.current_round - 1]
            
            send_round_advancement_email(
                seeker_email=user.email,
                seeker_name=job_seeker.full_name,
                job_title=job.title,
                company_name=job.employer.company_name,
                round_number=application.current_round,
                round_title=next_round_data.get('title', 'Next Round'),
                round_type=next_round_data.get('type', 'interview'),
                instructions=next_round_data.get('instructions')
            )
        except Exception as e:
            print(f"Failed to send advancement email: {e}")
        
    db.commit()
    db.refresh(application)
    return application
# app/crud/application_crud.py
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from app.models.application import Application, ApplicationStatus
from app.models.job import Job
from app.models.job_seeker import JobSeeker
from app.models.employer import Employer
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
        skills_match=skills_match
    )
    
    db.add(application)
    db.commit()
    db.refresh(application)
    
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
    skip: int = 0,
    limit: int = 50
) -> List[Application]:
    """Get all applications for a job (employer view)"""
    query = db.query(Application).filter(Application.job_id == job_id)
    
    if status:
        query = query.filter(Application.status == status)
    
    if min_match_score:
        query = query.filter(Application.match_score >= min_match_score)
    
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

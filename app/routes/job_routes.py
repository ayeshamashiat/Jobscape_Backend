from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.schema.job_schema import JobCreate, JobUpdate, JobResponse, JobSearchResponse
from app.crud import job_crud, employer_crud
from app.utils.security import get_current_user
from app.models.user import User, UserRole
from app.models.subscription import JOB_POSTING_LIMITS
from app.models.job import Job
from app.models.job_seeker import JobSeeker
from app.crud.application_crud import calculate_match_score
import uuid
from datetime import datetime, timezone


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/", response_model=JobResponse, status_code=201)
def create_job(
    job_data: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create job with required application deadline"""

    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can post jobs")

    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(status_code=400, detail="Complete employer profile first")

    can_post, reason = employer.can_post_job()
    if not can_post:
        raise HTTPException(status_code=403, detail=reason)

    job = job_crud.create_job(db, employer_id=employer.id, **job_data.dict())

    employer.active_job_posts_count += 1
    employer.total_job_posts_count += 1
    db.commit()
    db.refresh(job)

    return job


@router.get("/", response_model=JobSearchResponse)
def search_jobs(
    # --- existing ---
    keyword: Optional[str] = Query(None),
    skills: Optional[str] = Query(None),           # comma-separated
    location: Optional[str] = Query(None),
    work_mode: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    experience_level: Optional[str] = Query(None),
    salary_min: Optional[int] = Query(None),
    fresh_grad_friendly: Optional[bool] = Query(None),
    # --- new (Feature 2) ---
    salary_max: Optional[int] = Query(None),
    industry: Optional[str] = Query(None),
    company_size: Optional[str] = Query(None),
    verification_tier: Optional[str] = Query(None),
    posted_within_days: Optional[int] = Query(None, ge=1, le=90),
    sort_by: str = Query("recent"),                 # 'recent' | 'salary_high' | 'salary_low'
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    skill_list = [s.strip() for s in skills.split(",") if s.strip()] if skills else None

    result = job_crud.search_jobs(
        db=db,
        keyword=keyword,
        skills=skill_list,
        location=location,
        work_mode=work_mode,
        job_type=job_type,
        experience_level=experience_level,
        salary_min=salary_min,
        salary_max=salary_max,
        fresh_grad_friendly=fresh_grad_friendly,
        industry=industry,
        company_size=company_size,
        verification_tier=verification_tier,
        posted_within_days=posted_within_days,
        sort_by=sort_by,
        skip=skip,
        limit=limit
    )
    return result


@router.get("/employer/my-jobs", response_model=List[JobResponse])
def get_my_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can view their jobs")

    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(status_code=400, detail="Employer profile not found")

    jobs = job_crud.get_jobs_by_employer(db, employer.id, skip, limit)
    return jobs


@router.get("/employer/posting-status")
def get_posting_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can access this")

    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(status_code=400, detail="Employer profile not found")

    job_limit = employer.get_job_posting_limit()
    can_post, reason = employer.can_post_job()

    return {
        "subscription_tier": employer.subscription_tier.value,
        "verification_tier": employer.verification_tier,
        "job_posting_limit": job_limit if job_limit != -1 else "unlimited",
        "active_jobs": employer.active_job_posts_count,
        "remaining_slots": (job_limit - employer.active_job_posts_count) if job_limit != -1 else "unlimited",
        "can_post_job": can_post,
        "message": reason,
        "all_limits": JOB_POSTING_LIMITS[employer.subscription_tier.value]
    }


# ===== NEW: Feature 5.1 — AI Match Score Preview =====
@router.get("/{job_id}/match-preview")
def get_match_preview(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns a match score (0–100) for the logged-in job seeker
    against this job — without creating an application.
    """
    if current_user.role != UserRole.JOB_SEEKER:
        raise HTTPException(status_code=403, detail="Only job seekers can use match preview")

    job = job_crud.get_job_by_id(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job_seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not job_seeker:
        raise HTTPException(status_code=400, detail="Complete your profile first")

    score, skills_match = calculate_match_score(job, job_seeker)

    return {
        "job_id": str(job_id),
        "match_score": score,
        "skills_match": skills_match
    }


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = job_crud.get_job_by_id(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.patch("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: uuid.UUID,
    job_data: JobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(status_code=403, detail="Unauthorized")

    try:
        job = job_crud.update_job(db, job_id, employer.id, **job_data.dict(exclude_unset=True))
        return job
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{job_id}")
def delete_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(status_code=403, detail="Unauthorized")

    try:
        job_crud.delete_job(db, job_id, employer.id)
        employer.active_job_posts_count = max(0, employer.active_job_posts_count - 1)
        db.commit()
        return {"message": "Job deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{job_id}/close")
def close_job_manually(
    job_id: uuid.UUID,
    reason: str = "filled",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(status_code=403, detail="Unauthorized")

    job = db.query(Job).filter(Job.id == job_id, Job.employer_id == employer.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.is_closed:
        raise HTTPException(status_code=400, detail="Job is already closed")

    job.is_active = False
    job.is_closed = True
    job.closed_at = datetime.now(timezone.utc)
    job.closure_reason = f"manual_{reason}"
    employer.active_job_posts_count = max(0, employer.active_job_posts_count - 1)
    db.commit()

    return {
        "message": "Job closed successfully",
        "job_id": str(job_id),
        "closure_reason": reason,
        "active_jobs_remaining": employer.active_job_posts_count
    }


@router.post("/{job_id}/reopen")
def reopen_job(
    job_id: uuid.UUID,
    new_deadline: datetime,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(status_code=403, detail="Unauthorized")

    job = db.query(Job).filter(Job.id == job_id, Job.employer_id == employer.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.is_closed:
        raise HTTPException(status_code=400, detail="Job is not closed")

    can_post, reason = employer.can_post_job()
    if not can_post:
        raise HTTPException(status_code=403, detail=reason)

    now = datetime.now(timezone.utc)
    if new_deadline <= now:
        raise HTTPException(status_code=400, detail="New deadline must be in the future")

    job.is_active = True
    job.is_closed = False
    job.closed_at = None
    job.application_deadline = new_deadline
    job.closure_reason = None
    employer.active_job_posts_count += 1
    db.commit()

    return {
        "message": "Job reopened successfully",
        "job_id": str(job_id),
        "new_deadline": new_deadline.isoformat(),
        "active_jobs": employer.active_job_posts_count
    }
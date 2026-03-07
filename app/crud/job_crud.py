from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, func, desc, asc
from app.models.job import Job
from app.models.employer import Employer
from typing import List, Optional, Dict
import uuid
from datetime import datetime, timezone, timedelta


def create_job(db: Session, employer_id: uuid.UUID, **job_data) -> Job:
    job = Job(employer_id=employer_id, **job_data)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job_by_id(db: Session, job_id: uuid.UUID) -> Optional[Job]:
    """Get job by ID, eagerly loading the employer for 'Posted By'."""
    return (
        db.query(Job)
        .options(joinedload(Job.employer))
        .filter(Job.id == job_id, Job.is_active == True)
        .first()
    )


def get_jobs_by_employer(db: Session, employer_id: uuid.UUID, skip: int = 0, limit: int = 20) -> List[Job]:
    return db.query(Job).filter(
        Job.employer_id == employer_id,
        Job.is_active == True
    ).offset(skip).limit(limit).all()


def update_job(db: Session, job_id: uuid.UUID, employer_id: uuid.UUID, **kwargs) -> Job:
    job = db.query(Job).filter(Job.id == job_id, Job.employer_id == employer_id).first()
    if not job:
        raise ValueError("Job not found or unauthorized")

    for key, value in kwargs.items():
        if hasattr(job, key) and value is not None:
            setattr(job, key, value)

    db.commit()
    db.refresh(job)
    return job


def delete_job(db: Session, job_id: uuid.UUID, employer_id: uuid.UUID):
    job = db.query(Job).filter(Job.id == job_id, Job.employer_id == employer_id).first()
    if not job:
        raise ValueError("Job not found or unauthorized")
    job.is_active = False
    db.commit()


def search_jobs(
    db: Session,
    keyword: Optional[str] = None,
    skills: Optional[List[str]] = None,
    location: Optional[str] = None,
    work_mode: Optional[str] = None,
    job_type: Optional[str] = None,
    experience_level: Optional[str] = None,
    salary_min: Optional[int] = None,
    salary_max: Optional[int] = None,           # NEW
    fresh_grad_friendly: Optional[bool] = None,
    industry: Optional[str] = None,             # NEW — filter by employer industry
    company_size: Optional[str] = None,         # NEW
    verification_tier: Optional[str] = None,    # NEW — only verified employers
    posted_within_days: Optional[int] = None,   # NEW — e.g. 7, 14, 30
    sort_by: str = 'recent',                    # NEW — 'recent' | 'salary_high' | 'salary_low'
    skip: int = 0,
    limit: int = 20
) -> Dict:
    # Join Employer so we can filter on employer fields
    query = (
        db.query(Job)
        .options(joinedload(Job.employer))
        .join(Employer, Job.employer_id == Employer.id)
        .filter(Job.is_active == True, Job.is_closed == False)
    )

    # --- existing filters ---
    if keyword:
        query = query.filter(
            or_(
                Job.title.ilike(f"%{keyword}%"),
                Job.description.ilike(f"%{keyword}%")
            )
        )

    if skills:
        skills = [s.strip() for s in skills if s.strip()]
        for skill in skills:
            query = query.filter(
                or_(
                    Job.required_skills.contains([skill]),
                    Job.preferred_skills.contains([skill])
                )
            )

    if location:
        query = query.filter(Job.location.ilike(f"%{location}%"))

    if work_mode:
        query = query.filter(Job.work_mode == work_mode)

    if job_type:
        query = query.filter(Job.job_type == job_type)

    if experience_level:
        query = query.filter(Job.experience_level == experience_level)

    if salary_min:
        query = query.filter(Job.salary_max >= salary_min)  # range overlaps

    # --- new filters ---
    if salary_max:
        query = query.filter(Job.salary_min <= salary_max)

    if fresh_grad_friendly is not None:
        query = query.filter(Job.is_fresh_graduate_friendly == fresh_grad_friendly)

    if industry:
        query = query.filter(Employer.industry.ilike(f"%{industry}%"))

    if company_size:
        query = query.filter(Employer.company_size == company_size)

    if verification_tier:
        query = query.filter(Employer.verification_tier == verification_tier)

    if posted_within_days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=posted_within_days)
        query = query.filter(Job.created_at >= cutoff)

    # --- sorting ---
    if sort_by == 'salary_high':
        query = query.order_by(desc(Job.salary_max))
    elif sort_by == 'salary_low':
        query = query.order_by(asc(Job.salary_min))
    else:
        query = query.order_by(desc(Job.created_at))  # default: recent

    total = query.count()
    jobs = query.offset(skip).limit(limit).all()

    page = (skip // limit) + 1 if limit > 0 else 1
    pages = (total + limit - 1) // limit if limit > 0 else 1

    return {
        "items": jobs,
        "total": total,
        "page": page,
        "pages": pages,
        "has_next": page < pages,
        "has_prev": page > 1
    }
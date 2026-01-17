from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from app.models.job import Job
from typing import List, Optional, Dict
import uuid

def create_job(db: Session, employer_id: uuid.UUID, **job_data) -> Job:
    job = Job(employer_id=employer_id, **job_data)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job

def get_job_by_id(db: Session, job_id: uuid.UUID) -> Optional[Job]:
    return db.query(Job).filter(Job.id == job_id, Job.is_active == True).first()

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
    fresh_grad_friendly: Optional[bool] = None,
    skip: int = 0,
    limit: int = 20
) -> Dict:
    query = db.query(Job).filter(Job.is_active == True)
    
    if keyword:
        search_filter = or_(
            Job.title.ilike(f"%{keyword}%"),
            Job.description.ilike(f"%{keyword}%")
        )
        query = query.filter(search_filter)
    
    if skills:
        # Filter out empty strings
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
        query = query.filter(Job.salary_min >= salary_min)
    
    if fresh_grad_friendly is not None:
        query = query.filter(Job.is_fresh_graduate_friendly == fresh_grad_friendly)
    
    # Get total count before pagination
    total = query.count()
    
    # Apply pagination
    jobs = query.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()
    
    # Calculate metadata
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

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.schema.job_schema import JobCreate, JobUpdate, JobResponse, JobSearchResponse
from app.crud import job_crud, employer_crud
from app.utils.security import get_current_user
from app.models.user import User, UserRole
import uuid

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.post("/", response_model=JobResponse, status_code=201)
def create_job(
    job_data: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can post jobs")
    
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(status_code=400, detail="Complete employer profile first")
    
    job = job_crud.create_job(db, employer_id=employer.id, **job_data.dict())
    return job

@router.get("/", response_model=JobSearchResponse)
def search_jobs(
    keyword: Optional[str] = Query(None),
    skills: Optional[str] = Query(None),  # comma-separated
    location: Optional[str] = Query(None),
    work_mode: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    experience_level: Optional[str] = Query(None),
    salary_min: Optional[int] = Query(None),
    fresh_grad_friendly: Optional[bool] = Query(None),
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
        fresh_grad_friendly=fresh_grad_friendly,
        skip=skip,
        limit=limit
    )
    return result

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
        return {"message": "Job deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

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

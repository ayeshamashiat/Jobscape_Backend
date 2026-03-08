import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.utils.security import get_current_user
from app.models.user import User, UserRole
from app.models.job_seeker import JobSeeker
from app.models.job import Job
from app.models.saved_job import SavedJob
from app.schema.job_schema import JobResponse

router = APIRouter(tags=["saved_jobs"])

@router.post("/jobs/{job_id}/save", status_code=status.HTTP_201_CREATED)
def save_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Save/bookmark a job for later"""
    if current_user.role != UserRole.JOB_SEEKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Only job seekers can save jobs"
        )

    job_seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not job_seeker:
        raise HTTPException(status_code=404, detail="Job seeker profile not found")

    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    existing_save = db.query(SavedJob).filter(
        SavedJob.job_seeker_id == job_seeker.id,
        SavedJob.job_id == job_id
    ).first()

    if existing_save:
        raise HTTPException(status_code=400, detail="Job is already saved")

    saved_job = SavedJob(job_seeker_id=job_seeker.id, job_id=job_id)
    db.add(saved_job)
    db.commit()

    return {"message": "Job saved successfully", "job_id": str(job_id)}


@router.delete("/jobs/{job_id}/save", status_code=status.HTTP_200_OK)
def unsave_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove a saved/bookmarked job"""
    if current_user.role != UserRole.JOB_SEEKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Only job seekers can unsave jobs"
        )

    job_seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not job_seeker:
        raise HTTPException(status_code=404, detail="Job seeker profile not found")

    saved_job = db.query(SavedJob).filter(
        SavedJob.job_seeker_id == job_seeker.id,
        SavedJob.job_id == job_id
    ).first()

    if not saved_job:
        raise HTTPException(status_code=404, detail="Job is not saved")

    db.delete(saved_job)
    db.commit()

    return {"message": "Job removed from saved list", "job_id": str(job_id)}


@router.get("/jobseeker/saved-jobs", response_model=List[JobResponse])
def get_saved_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all saved/bookmarked jobs for the current job seeker"""
    if current_user.role != UserRole.JOB_SEEKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Only job seekers can view saved jobs"
        )

    job_seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not job_seeker:
        raise HTTPException(status_code=404, detail="Job seeker profile not found")

    saved_jobs = db.query(SavedJob).filter(
        SavedJob.job_seeker_id == job_seeker.id
    ).order_by(SavedJob.saved_at.desc()).all()

    jobs = [sj.job for sj in saved_jobs]
    return jobs

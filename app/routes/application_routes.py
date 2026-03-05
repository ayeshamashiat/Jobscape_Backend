# app/routes/application_routes.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.utils.security import get_current_user
from app.models.user import User, UserRole
from app.models.application import ApplicationStatus
from app.schema.application_schema import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationDetailResponse,
    EmployerApplicationUpdate,
    ApplicationStatsResponse
)
from app.crud import application_crud, employer_crud
import uuid

from app.crud.application_crud import score_application_ats, bulk_score_job_applications

router = APIRouter(prefix="/applications", tags=["applications"])


# ===== JOB SEEKER ROUTES =====

@router.post("/", response_model=ApplicationResponse, status_code=201)
def apply_to_job(
    application_data: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Job seeker applies to a job"""
    
    if current_user.role != UserRole.JOB_SEEKER:
        raise HTTPException(status_code=403, detail="Only job seekers can apply")
    
    # Get job seeker ID
    from app.models.job_seeker import JobSeeker
    job_seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not job_seeker:
        raise HTTPException(status_code=400, detail="Complete your profile first")
    
    try:
        application = application_crud.create_application(
            db=db,
            job_id=application_data.job_id,
            job_seeker_id=job_seeker.id,
            resume_id=application_data.resume_id,
            cover_letter=application_data.cover_letter
        )
        
        return application
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/my-applications", response_model=List[ApplicationResponse])
def get_my_applications(
    status: Optional[ApplicationStatus] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all applications by current job seeker"""
    
    if current_user.role != UserRole.JOB_SEEKER:
        raise HTTPException(status_code=403, detail="Only job seekers can view their applications")
    
    from app.models.job_seeker import JobSeeker
    job_seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    
    applications = application_crud.get_job_seeker_applications(
        db=db,
        job_seeker_id=job_seeker.id,
        status=status,
        skip=skip,
        limit=limit
    )
    
    # Enrich with job details
    from app.models.job import Job
    from app.models.employer import Employer
    
    result = []
    for app in applications:
        job = db.query(Job).filter(Job.id == app.job_id).first()
        employer = db.query(Employer).filter(Employer.id == job.employer_id).first()
        
        app_dict = app.__dict__
        app_dict["job_title"] = job.title if job else None
        app_dict["company_name"] = employer.company_name if employer else None
        result.append(app_dict)
    
    return result


@router.get("/{application_id}", response_model=ApplicationDetailResponse)
def get_application_details(
    application_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get application details"""
    
    application = application_crud.get_application_by_id(db, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    
    # Check authorization
    from app.models.job_seeker import JobSeeker
    from app.models.job import Job
    
    if current_user.role == UserRole.JOB_SEEKER:
        job_seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
        if application.job_seeker_id != job_seeker.id:
            raise HTTPException(status_code=403, detail="Unauthorized")
    
    elif current_user.role == UserRole.EMPLOYER:
        employer = employer_crud.get_employer_by_user_id(db, current_user.id)
        job = db.query(Job).filter(Job.id == application.job_id).first()
        if job.employer_id != employer.id:
            raise HTTPException(status_code=403, detail="Unauthorized")
    
    else:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    return application


@router.post("/{application_id}/withdraw", response_model=ApplicationResponse)
def withdraw_application(
    application_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Withdraw application"""
    
    if current_user.role != UserRole.JOB_SEEKER:
        raise HTTPException(status_code=403, detail="Only job seekers can withdraw applications")
    
    from app.models.job_seeker import JobSeeker
    job_seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    
    try:
        application = application_crud.withdraw_application(db, application_id, job_seeker.id)
        return application
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ===== EMPLOYER ROUTES =====

@router.get("/job/{job_id}/applications", response_model=List[ApplicationResponse])
def get_job_applications(
    job_id: uuid.UUID,
    status: Optional[ApplicationStatus] = Query(None),
    min_match_score: Optional[int] = Query(None, ge=0, le=100),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all applications for a job (employer only)"""
    
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can view job applications")
    
    # Verify employer owns this job
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    from app.models.job import Job
    job = db.query(Job).filter(Job.id == job_id).first()
    
    if not job or job.employer_id != employer.id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    applications = application_crud.get_job_applications(
        db=db,
        job_id=job_id,
        status=status,
        min_match_score=min_match_score,
        skip=skip,
        limit=limit
    )
    
    # Enrich with job seeker details
    from app.models.job_seeker import JobSeeker
    from app.models.user import User
    
    result = []
    for app in applications:
        job_seeker = db.query(JobSeeker).filter(JobSeeker.id == app.job_seeker_id).first()
        user = db.query(User).filter(User.id == job_seeker.user_id).first()
        
        app_dict = app.__dict__
        app_dict["applicant_name"] = job_seeker.full_name if job_seeker else None
        app_dict["applicant_email"] = user.email if user else None
        result.append(app_dict)
    
    return result


@router.get("/employer/all-applications", response_model=List[ApplicationResponse])
def get_all_employer_applications(
    status: Optional[ApplicationStatus] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all applications across all employer's jobs"""
    
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can view applications")
    
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    
    applications = application_crud.get_employer_applications(
        db=db,
        employer_id=employer.id,
        status=status,
        skip=skip,
        limit=limit
    )
    
    return applications


@router.patch("/{application_id}/status", response_model=ApplicationDetailResponse)
def update_application_status(
    application_id: uuid.UUID,
    update_data: EmployerApplicationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Employer updates application status"""
    
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can update application status")
    
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    
    try:
        application = application_crud.update_application_status(
            db=db,
            application_id=application_id,
            employer_id=employer.id,
            status=update_data.status,
            employer_notes=update_data.employer_notes,
            rejection_reason=update_data.rejection_reason,
            interview_scheduled_at=update_data.interview_scheduled_at,
            interview_location=update_data.interview_location,
            interview_notes=update_data.interview_notes
        )
        return application
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/job/{job_id}/stats", response_model=ApplicationStatsResponse)
def get_job_application_stats(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get application statistics for a job"""
    
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can view stats")
    
    # Verify employer owns this job
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    from app.models.job import Job
    job = db.query(Job).filter(Job.id == job_id).first()
    
    if not job or job.employer_id != employer.id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    stats = application_crud.get_application_stats(db, job_id)
    return stats



@router.get("/{application_id}/details")
def get_job_application_details(
    application_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get full application details including job seeker profile and resume
    (Employer only)
    """
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can access this")
    
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    
    details = application_crud.get_application_full_details(
        db=db,
        application_id=application_id,
        employer_id=employer.id
    )
    
    if not details:
        raise HTTPException(status_code=404, detail="Application not found or unauthorized")
    
    return details


@router.get("/{application_id}/resume")
def get_application_resume(
    application_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get resume details for an application (employer only)"""
    
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can access this")
    
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    
    resume_data = application_crud.get_application_resume(
        db=db,
        application_id=application_id,
        employer_id=employer.id
    )
    
    if not resume_data:
        raise HTTPException(
            status_code=404, 
            detail="Resume not found or no access"
        )
    
    return resume_data

@router.post("/job/{job_id}/bulk-ats-score")
def bulk_ats_score(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger ATS scoring for ALL applications of a job."""
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can trigger ATS scoring")

    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    try:
        result = bulk_score_job_applications(db, job_id, employer.id)
        return {"message": "Bulk ATS scoring complete", **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{application_id}/ats-score")
async def score_single_application(
    application_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ATS score a single application."""
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can trigger ATS scoring")

    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    try:
        application = await score_application_ats(db, application_id, employer.id)
        return {
            "application_id": str(application.id),
            "ats_score": application.ats_score,
            "ats_report": application.ats_report,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/job/{job_id}/ats-ranked")
def get_ats_ranked_applications(
    job_id: uuid.UUID,
    min_score: int = Query(0, ge=0, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all applications for a job ranked by ATS score."""
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can access this")

    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    from app.models.job import Job
    job = db.query(Job).filter(Job.id == job_id, Job.employer_id == employer.id).first()
    if not job:
        raise HTTPException(status_code=403, detail="Unauthorized")

    from app.models.jobseeker import JobSeeker
    applications = (
        db.query(Application)
        .filter(
            Application.job_id == job_id,
            Application.ats_score >= min_score
        )
        .order_by(Application.ats_score.desc())
        .all()
    )

    result = []
    for app in applications:
        js = db.query(JobSeeker).filter(JobSeeker.id == app.job_seeker_id).first()
        result.append({
            "application_id": str(app.id),
            "applicant_name": js.full_name if js else None,
            "ats_score": app.ats_score,
            "match_score": app.match_score,
            "recommendation": app.ats_report.get("recommendation") if app.ats_report else None,
            "status": app.status,
        })

    return {"job_id": str(job_id), "total": len(result), "applications": result}

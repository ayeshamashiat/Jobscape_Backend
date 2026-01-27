from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone, timedelta
from app.database import get_db
from app.schema.employer_schema import (
    EmployerRegistrationCreate,
    EmployerProfileUpdate,
    EmployerProfileResponse,
    WorkEmailVerificationConfirm,
    WorkEmailVerificationStatusResponse
)
from app.schema.job_schema import (
    JobCreate,
    JobUpdate,
    JobResponse,
    JobWithApplicationsResponse,
    JobStatsResponse,
    JobSearchResponse
)
from app.schema.employer_schema import (
    EmployerDashboardStats,
    JobApplicationSummary
)
from app.models.job import Job
from app.models.application import Application
from sqlalchemy import func, desc
from typing import List
from app.schema.user_schema import UserCreate, UserResponse
from app.crud import user_crud
from app.crud import employer_crud
from app.crud.auth_crud import create_email_verification_token, verify_email, verify_work_email, resend_work_email_verification, create_work_email_verification_token
from app.models.employer import Employer
from app.models.user import User, UserRole
from app.utils.security import get_current_user
from app.utils.email import send_verification_email, send_work_email_verification
from app.utils.file_validators import validate_image_file, validate_document_file
from app.utils.email_validators import verify_work_email_ownership
from app.utils.startup_verifier import verify_linkedin_company, verify_website_legitimacy, calculate_startup_trust_score
import cloudinary.uploader
import os

router = APIRouter(prefix="/employer", tags=["employer"])

# ============== DEV MODE CONFIGURATION ==============
DEV_MODE = os.getenv("ENVIRONMENT", "development") == "development"
DEV_VERIFICATION_CODE = "123456"
# ====================================================


# ===== SIMPLE REGISTRATION (Step 1) =====
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_employer(user: UserCreate, db: Session = Depends(get_db)):
    """
    Step 1: Register a new employer account - basic info only
    
    DEV MODE: Returns verification code in response
    PRODUCTION: Sends verification email
    """
    
    # Check if user already exists
    existing_user = user_crud.get_user_by_email(db, user.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    new_user = user_crud.create_user(db, user.email, UserRole.EMPLOYER, user.password)
    
    # Create employer profile with placeholder work_email
    employer = Employer(
        user_id=new_user.id,
        full_name=user.full_name,
        work_email=user.email,  # Placeholder
        company_name=user.full_name,
        company_email=user.email
    )
    
    db.add(employer)
    db.commit()
    db.refresh(employer)
    
    # ============== EMAIL VERIFICATION ==============
    if DEV_MODE:
        # DEV: Return code directly
        new_user.__dict__['dev_verification_code'] = DEV_VERIFICATION_CODE
        new_user.__dict__['dev_mode'] = True
    else:
        # PRODUCTION: Send verification email
        token = create_email_verification_token(db, new_user)
        send_verification_email(new_user.email, token)
    # ================================================
    
    return new_user


# ===== VERIFY EMAIL (Step 1.5) =====
@router.post("/verify-email")
def verify_user_email(
    email: str = Form(...),
    code: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Verify user email address
    
    DEV MODE: Accepts code "123456"
    PRODUCTION: Validates against database token
    """
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")
    
    # ============== DEV MODE BYPASS ==============
    if DEV_MODE and code == DEV_VERIFICATION_CODE:
        user.is_email_verified = True
        user.email_verification_token = None
        user.email_verification_expiry = None
        db.commit()
        return {
            "message": "Email verified successfully!",
            "dev_mode": True
        }
    # =============================================
    
    # ============== PRODUCTION LOGIC ==============
    # Validate token from database
    if not user.email_verification_token:
        raise HTTPException(
            status_code=400,
            detail="No verification token found. Please request a new verification email."
        )
    
    # Check if token matches
    if user.email_verification_token != code:
        raise HTTPException(status_code=400, detail="Invalid verification code")
    
    # Check if expired (24 hours)
    if not user.email_verification_expiry:
        raise HTTPException(status_code=400, detail="Verification token expired")
    
    if datetime.now(timezone.utc) > user.email_verification_expiry:
        raise HTTPException(
            status_code=400,
            detail="Verification code expired. Please request a new one."
        )
    
    # Mark as verified
    user.is_email_verified = True
    user.email_verification_token = None
    user.email_verification_expiry = None
    db.commit()
    
    return {
        "message": "Email verified successfully!",
        "email": user.email
    }
    # ==============================================


# ===== RESEND EMAIL VERIFICATION =====
@router.post("/verify-email/resend")
def resend_email_verification(
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    """Resend email verification code"""
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        # Don't reveal if email exists (security)
        return {"message": "If email exists, verification code has been sent"}
    
    if user.is_email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")
    
    # ============== DEV MODE ==============
    if DEV_MODE:
        return {
            "message": f"Verification code: {DEV_VERIFICATION_CODE}",
            "dev_mode": True,
            "dev_code": DEV_VERIFICATION_CODE
        }
    # ======================================
    
    # PRODUCTION: Generate and send new token
    token = create_email_verification_token(db, user)
    send_verification_email(user.email, token)
    
    return {"message": "Verification email sent"}


# ===== COMPLETE REGISTRATION (Step 2) =====
@router.post("/register/complete", response_model=EmployerProfileResponse, status_code=status.HTTP_201_CREATED)
def complete_employer_registration(
    profile_data: EmployerRegistrationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Step 2: Complete employer registration
    Sends work email verification code
    """

    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can use this endpoint")

    # Check if already completed
    existing = employer_crud.get_employer_by_user_id(db, current_user.id)
    if existing and existing.profile_completed:
        raise HTTPException(status_code=400, detail="Registration already completed")

    # Validate email domain for REGISTERED companies
    if profile_data.company_type == "REGISTERED":
        if not profile_data.company_website:
            raise HTTPException(status_code=400, detail="Registered companies must provide website")

        is_valid, error_msg = verify_work_email_ownership(
            profile_data.work_email,
            profile_data.company_website
        )
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

    # Create/Update employer profile
    try:
        employer = employer_crud.create_or_update_employer_registration(
            db=db,
            user_id=current_user.id,
            full_name=profile_data.full_name,
            job_title=profile_data.job_title,
            work_email=profile_data.work_email,
            company_name=profile_data.company_name,
            company_website=profile_data.company_website,
            industry=profile_data.industry,
            location=profile_data.location,
            company_size=profile_data.company_size,
            description=profile_data.description
        )

        # Set company type
        if hasattr(employer, 'company_type'):
            employer.company_type = profile_data.company_type
        if hasattr(employer, 'is_startup'):
            employer.is_startup = profile_data.is_startup
        if hasattr(employer, 'startup_stage'):
            employer.startup_stage = profile_data.startup_stage
        if hasattr(employer, 'founded_year'):
            employer.founded_year = profile_data.founded_year

        # Start with UNVERIFIED tier
        employer.verification_tier = "UNVERIFIED"
        employer.trust_score = 20
        employer.work_email_verified = False

        db.commit()
        db.refresh(employer)

        # ============== WORK EMAIL VERIFICATION ==============
        if DEV_MODE:
            # DEV: Code will be shown in frontend (123456)
            pass
        else:
            # PRODUCTION: Send verification email
            code = create_work_email_verification_token(db, employer)
            send_work_email_verification(
                to_email=employer.work_email,
                code=code,
                company_name=employer.company_name
            )
        # ====================================================

        return employer

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ===== VERIFY WORK EMAIL =====
@router.post("/verify-work-email/confirm")
def confirm_work_email_verification(
    request: WorkEmailVerificationConfirm,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Verify work email with 6-digit code
    Grants EMAIL_VERIFIED tier
    
    DEV MODE: Accepts "123456"
    PRODUCTION: Validates against database
    """
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can use this endpoint")

    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(status_code=404, detail="Employer profile not found")

    # ============== DEV MODE BYPASS ==============
    if DEV_MODE and request.verification_code == DEV_VERIFICATION_CODE:
        employer.work_email_verified = True
        employer.work_email_verified_at = datetime.now(timezone.utc)
        employer.verification_tier = "EMAIL_VERIFIED"
        employer.trust_score = 50
        employer.work_email_verification_token = None
        db.commit()
        db.refresh(employer)
        
        return {
            "message": "Work email verified successfully! (DEV MODE)",
            "verification_tier": employer.verification_tier,
            "trust_score": employer.trust_score,
            "verified_at": employer.work_email_verified_at,
            "can_post_jobs": True,
            "dev_mode": True
        }
    # =============================================

    # ============== PRODUCTION LOGIC ==============
    try:
        employer = verify_work_email(db, employer.id, request.verification_code)

        return {
            "message": "Work email verified successfully!",
            "verification_tier": employer.verification_tier,
            "trust_score": employer.trust_score,
            "verified_at": employer.work_email_verified_at,
            "can_post_jobs": employer.verification_tier in ["EMAIL_VERIFIED", "DOCUMENT_VERIFIED", "FULLY_VERIFIED"]
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # ==============================================


# ===== RESEND WORK EMAIL VERIFICATION =====
@router.post("/verify-work-email/resend")
def resend_work_email_code(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Resend work email verification code
    Rate limited: 1 request per 2 minutes
    
    DEV MODE: Always returns "123456"
    """
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can use this endpoint")

    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(status_code=404, detail="Employer profile not found")

    # ============== DEV MODE ==============
    if DEV_MODE:
        return {
            "message": f"Verification code: {DEV_VERIFICATION_CODE}",
            "expires_in_minutes": 15,
            "dev_mode": True,
            "dev_code": DEV_VERIFICATION_CODE
        }
    # ======================================

    # PRODUCTION
    try:
        code = resend_work_email_verification(db, employer.id)
        send_work_email_verification(
            to_email=employer.work_email,
            code=code,
            company_name=employer.company_name
        )

        return {
            "message": f"Verification code sent to {employer.work_email}",
            "expires_in_minutes": 15
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ===== CHECK WORK EMAIL VERIFICATION STATUS =====
@router.get("/verify-work-email/status", response_model=WorkEmailVerificationStatusResponse)
def get_work_email_verification_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check if work email is verified"""
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can use this endpoint")

    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(status_code=404, detail="Employer profile not found")

    # Check if code expired
    code_expired = False
    if employer.work_email_verification_sent_at and not employer.work_email_verified:
        expiry_time = employer.work_email_verification_sent_at + timedelta(minutes=15)
        code_expired = datetime.now(timezone.utc) > expiry_time

    return WorkEmailVerificationStatusResponse(
        work_email=employer.work_email,
        work_email_verified=employer.work_email_verified,
        verification_sent_at=employer.work_email_verification_sent_at,
        code_expired=code_expired,
        can_resend=not employer.work_email_verified,
        verification_tier=employer.verification_tier
    )


# ===== PROFILE MANAGEMENT =====
@router.get("/profile/me", response_model=EmployerProfileResponse)
def get_my_employer_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current employer's profile"""
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(status_code=404, detail="Employer profile not found")
    return employer


@router.patch("/profile", response_model=EmployerProfileResponse)
def update_employer_profile(
    profile_data: EmployerProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update employer profile"""
    try:
        employer = employer_crud.update_employer_profile(
            db=db,
            user_id=current_user.id,
            **profile_data.dict(exclude_unset=True)
        )
        return employer
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ===== VERIFICATION SUBMISSION =====
@router.post("/verification/submit-documents")
async def submit_verification_documents(
    # Form fields
    rjsc_registration_number: Optional[str] = Form(None),
    trade_license_number: Optional[str] = Form(None),
    tin_number: Optional[str] = Form(None),
    linkedin_company_url: Optional[str] = Form(None),
    additional_notes: Optional[str] = Form(None),
    
    # File uploads
    incorporation_cert: Optional[UploadFile] = File(None),
    trade_license: Optional[UploadFile] = File(None),
    tin_certificate: Optional[UploadFile] = File(None),
    business_card: Optional[UploadFile] = File(None),
    
    # Dependencies
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Submit company verification documents"""
    
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can request verification")
    
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(status_code=400, detail="Complete employer profile first")
    
    if hasattr(employer, 'profile_completed') and not employer.profile_completed:
        raise HTTPException(status_code=400, detail="Complete registration first")
    
    if hasattr(employer, 'verification_tier') and employer.verification_tier == "FULLY_VERIFIED":
        raise HTTPException(status_code=400, detail="Already fully verified")
    
    # Validation
    has_valid_submission = (
        (rjsc_registration_number and incorporation_cert) or
        (trade_license_number and trade_license) or
        (tin_number and tin_certificate)
    )
    
    if not has_valid_submission:
        raise HTTPException(
            status_code=400,
            detail="Must provide at least ONE complete document set (number + file)"
        )
    
    # Upload documents
    uploaded_docs = []
    
    try:
        if incorporation_cert:
            file_content = await validate_document_file(incorporation_cert)
            result = cloudinary.uploader.upload(
                file_content,
                folder=f"jobscape/verification/{employer.id}",
                resource_type="auto",
                public_id=f"incorporation_{int(datetime.now().timestamp())}"
            )
            uploaded_docs.append({
                "type": "incorporation_certificate",
                "url": result["secure_url"],
                "public_id": result["public_id"],
                "filename": incorporation_cert.filename,
                "uploaded_at": datetime.now(timezone.utc).isoformat()
            })
        
        if trade_license:
            file_content = await validate_document_file(trade_license)
            result = cloudinary.uploader.upload(
                file_content,
                folder=f"jobscape/verification/{employer.id}",
                resource_type="auto",
                public_id=f"trade_license_{int(datetime.now().timestamp())}"
            )
            uploaded_docs.append({
                "type": "trade_license",
                "url": result["secure_url"],
                "public_id": result["public_id"],
                "filename": trade_license.filename,
                "uploaded_at": datetime.now(timezone.utc).isoformat()
            })
        
        if tin_certificate:
            file_content = await validate_document_file(tin_certificate)
            result = cloudinary.uploader.upload(
                file_content,
                folder=f"jobscape/verification/{employer.id}",
                resource_type="auto",
                public_id=f"tin_{int(datetime.now().timestamp())}"
            )
            uploaded_docs.append({
                "type": "tin_certificate",
                "url": result["secure_url"],
                "public_id": result["public_id"],
                "filename": tin_certificate.filename,
                "uploaded_at": datetime.now(timezone.utc).isoformat()
            })
        
        if business_card:
            file_content = await validate_document_file(business_card)
            result = cloudinary.uploader.upload(
                file_content,
                folder=f"jobscape/verification/{employer.id}",
                resource_type="auto",
                public_id=f"business_card_{int(datetime.now().timestamp())}"
            )
            uploaded_docs.append({
                "type": "business_card",
                "url": result["secure_url"],
                "public_id": result["public_id"],
                "filename": business_card.filename,
                "uploaded_at": datetime.now(timezone.utc).isoformat()
            })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"File upload failed: {str(e)}")
    
    # Update employer
    notes_parts = [f"Submitted: {datetime.now(timezone.utc).isoformat()}"]
    if linkedin_company_url:
        notes_parts.append(f"LinkedIn: {linkedin_company_url}")
    if additional_notes:
        notes_parts.append(f"Notes: {additional_notes}")
    
    if hasattr(employer, 'verification_notes') and employer.verification_notes:
        notes_parts.append(f"\n--- Previous Notes ---\n{employer.verification_notes}")
    
    if hasattr(employer, 'verification_tier'):
        employer.verification_tier = "DOCUMENT_VERIFIED"
    if hasattr(employer, 'verification_documents'):
        employer.verification_documents = uploaded_docs
    if hasattr(employer, 'rjsc_registration_number'):
        employer.rjsc_registration_number = rjsc_registration_number
    if hasattr(employer, 'trade_license_number'):
        employer.trade_license_number = trade_license_number
    if hasattr(employer, 'tin_number'):
        employer.tin_number = tin_number
    if hasattr(employer, 'verification_notes'):
        employer.verification_notes = "\n".join(notes_parts)
    if hasattr(employer, 'trust_score'):
        employer.trust_score = min(employer.trust_score + 15, 100)
    
    db.commit()
    db.refresh(employer)
    
    return {
        "message": "Documents submitted! Upgraded to DOCUMENT_VERIFIED.",
        "verification_tier": getattr(employer, 'verification_tier', 'UNKNOWN'),
        "trust_score": getattr(employer, 'trust_score', 0),
        "documents_uploaded": len(uploaded_docs)
    }


@router.get("/verification/status")
def get_verification_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current verification status"""
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(status_code=404, detail="Employer profile not found")
    
    verification_tier = getattr(employer, 'verification_tier', 'UNVERIFIED')
    verified_at = getattr(employer, 'verified_at', None)
    verification_docs = getattr(employer, 'verification_documents', [])
    trust_score = getattr(employer, 'trust_score', 0)
    
    return {
        "status": verification_tier,
        "verified_at": verified_at,
        "documents_submitted": len(verification_docs) if verification_docs else 0,
        "trust_score": trust_score,
        "can_submit": verification_tier in ["UNVERIFIED", "EMAIL_VERIFIED", "REJECTED"]
    }

# ====================== DASHBOARD ======================

@router.get("/dashboard/stats", response_model=EmployerDashboardStats)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get dashboard statistics for employer"""
    
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only employers can access dashboard"
        )
    
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employer profile not found"
        )
    
    # Get job stats
    total_jobs = db.query(Job).filter(Job.employer_id == employer.id).count()
    active_jobs = db.query(Job).filter(
        Job.employer_id == employer.id,
        Job.is_active == True,
        Job.is_closed == False
    ).count()
    closed_jobs = db.query(Job).filter(
        Job.employer_id == employer.id,
        Job.is_closed == True
    ).count()
    
    # Get application stats
    job_ids = db.query(Job.id).filter(Job.employer_id == employer.id).subquery()
    
    total_applications = db.query(Application).filter(
        Application.job_id.in_(job_ids)
    ).count()
    
    pending_applications = db.query(Application).filter(
        Application.job_id.in_(job_ids),
        Application.status == "PENDING"
    ).count()
    
    shortlisted_applications = db.query(Application).filter(
        Application.job_id.in_(job_ids),
        Application.status == "SHORTLISTED"
    ).count()
    
    rejected_applications = db.query(Application).filter(
        Application.job_id.in_(job_ids),
        Application.status == "REJECTED"
    ).count()
    
    return EmployerDashboardStats(
        total_jobs_posted=total_jobs,
        active_jobs=active_jobs,
        closed_jobs=closed_jobs,
        total_applications=total_applications,
        pending_applications=pending_applications,
        shortlisted_applications=shortlisted_applications,
        rejected_applications=rejected_applications
    )


# ====================== JOB MANAGEMENT ======================

@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    data: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new job posting"""
    
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only employers can post jobs"
        )
    
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employer profile not found"
        )
    
    # Check if work email is verified (required for posting jobs)
    if not employer.work_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your work email before posting jobs"
        )
    
    # Validate salary range
    if data.salary_min and data.salary_max:
        if data.salary_max < data.salary_min:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Salary max must be greater than salary min"
            )
    
    # Create job
    job = Job(
        employer_id=employer.id,
        title=data.title,
        description=data.description,
        salary_min=data.salary_min,
        salary_max=data.salary_max,
        location=data.location,
        work_mode=data.work_mode,
        job_type=data.job_type,
        experience_level=data.experience_level,
        required_skills=data.required_skills,
        preferred_skills=data.preferred_skills,
        is_fresh_graduate_friendly=data.is_fresh_graduate_friendly,
        application_deadline=data.application_deadline,
        is_active=True,
        is_closed=False
    )
    
    db.add(job)
    db.commit()
    db.refresh(job)
    
    return job


@router.get("/jobs", response_model=List[JobWithApplicationsResponse])
def get_my_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all jobs posted by current employer"""
    
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only employers can access this endpoint"
        )
    
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employer profile not found"
        )
    
    # Build query
    query = db.query(Job).filter(Job.employer_id == employer.id)
    
    if is_active is not None:
        query = query.filter(Job.is_active == is_active)
    
    # Get jobs
    jobs = query.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()
    
    # Add application counts
    result = []
    for job in jobs:
        total_apps = db.query(Application).filter(Application.job_id == job.id).count()
        new_apps = db.query(Application).filter(
            Application.job_id == job.id,
            Application.status == "PENDING"
        ).count()
        
        job_dict = JobWithApplicationsResponse(
            **job.__dict__,
            total_applications=total_apps,
            new_applications=new_apps,
            company_name=employer.company_name
        )
        result.append(job_dict)
    
    return result


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific job by ID"""
    
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only employers can access this endpoint"
        )
    
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employer profile not found"
        )
    
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.employer_id == employer.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return job


@router.patch("/jobs/{job_id}", response_model=JobResponse)
def update_job(
    job_id: str,
    data: JobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a job posting"""
    
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only employers can update jobs"
        )
    
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employer profile not found"
        )
    
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.employer_id == employer.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Update fields
    update_data = data.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        if hasattr(job, field):
            setattr(job, field, value)
    
    db.commit()
    db.refresh(job)
    
    return job


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a job posting"""
    
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only employers can delete jobs"
        )
    
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employer profile not found"
        )
    
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.employer_id == employer.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    db.delete(job)
    db.commit()
    
    return None


@router.post("/jobs/{job_id}/close")
def close_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Close a job posting"""
    
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only employers can close jobs"
        )
    
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employer profile not found"
        )
    
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.employer_id == employer.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    job.is_active = False
    job.is_closed = True
    
    db.commit()
    
    return {"message": "Job closed successfully"}


@router.post("/jobs/{job_id}/reopen")
def reopen_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Reopen a closed job"""
    
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only employers can reopen jobs"
        )
    
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employer profile not found"
        )
    
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.employer_id == employer.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    job.is_active = True
    job.is_closed = False
    
    db.commit()
    
    return {"message": "Job reopened successfully"}


@router.get("/jobs/{job_id}/stats", response_model=JobStatsResponse)
def get_job_stats(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get statistics for a specific job"""
    
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only employers can access job stats"
        )
    
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employer profile not found"
        )
    
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.employer_id == employer.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Get application stats
    total_apps = db.query(Application).filter(Application.job_id == job.id).count()
    pending_apps = db.query(Application).filter(
        Application.job_id == job.id,
        Application.status == "PENDING"
    ).count()
    shortlisted_apps = db.query(Application).filter(
        Application.job_id == job.id,
        Application.status == "SHORTLISTED"
    ).count()
    rejected_apps = db.query(Application).filter(
        Application.job_id == job.id,
        Application.status == "REJECTED"
    ).count()
    
    acceptance_rate = (shortlisted_apps / total_apps * 100) if total_apps > 0 else 0.0
    
    return JobStatsResponse(
        job_id=job.id,
        job_title=job.title,
        views=0,  # Implement view tracking later if needed
        total_applications=total_apps,
        pending_applications=pending_apps,
        shortlisted_applications=shortlisted_apps,
        rejected_applications=rejected_apps,
        acceptance_rate=acceptance_rate
    )
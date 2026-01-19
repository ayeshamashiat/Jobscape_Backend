from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone, timedelta
from app.database import get_db
from app.schema.employer_schema import (
    EmployerRegistrationCreate,
    EmployerProfileUpdate,
    EmployerProfileResponse
)
from app.schema.employer_schema import (
    EmployerRegistrationCreate,
    EmployerProfileUpdate,
    EmployerProfileResponse,
    WorkEmailVerificationConfirm,
    WorkEmailVerificationStatusResponse
)
from app.schema.user_schema import UserCreate, UserResponse
from app.crud import user_crud
from app.crud import employer_crud
from app.crud.auth_crud import create_email_verification_token, verify_work_email, resend_work_email_verification, create_work_email_verification_token  # ← ADD THIS
from app.models.employer import Employer
from app.utils.security import get_current_user
from app.utils.email import send_verification_email, send_work_email_verification
from app.utils.file_validators import validate_image_file, validate_document_file
from app.utils.email_validators import verify_work_email_ownership
from app.utils.startup_verifier import verify_linkedin_company, verify_website_legitimacy, calculate_startup_trust_score
from app.models.user import User, UserRole
import cloudinary.uploader


router = APIRouter(prefix="/employer", tags=["employer"])


# ===== SIMPLE REGISTRATION (Step 1) =====
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_employer(user: UserCreate, db: Session = Depends(get_db)):
    """Step 1: Register a new employer account - basic info only"""
    
    # Check if user already exists
    existing_user = user_crud.get_user_by_email(db, user.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    new_user = user_crud.create_user(db, user.email, UserRole.EMPLOYER, user.password)
    
    # ✅ FIX: Add work_email as placeholder
    employer = Employer(
        user_id=new_user.id,
        full_name=user.full_name,
        work_email=user.email,           # ← USE EMAIL AS PLACEHOLDER
        company_name=user.full_name,
        company_email=user.email
    )
    
    db.add(employer)
    db.commit()
    db.refresh(employer)
    
    # Send verification email
    token = create_email_verification_token(db, new_user)
    send_verification_email(new_user.email, token)
    
    return new_user

# ===== COMPLETE REGISTRATION (Step 2) =====

@router.post("/register/complete", response_model=EmployerProfileResponse, status_code=status.HTTP_201_CREATED)
def complete_employer_registration(
    profile_data: EmployerRegistrationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Step 2: Complete employer registration
    NOW: Sends work email verification code instead of granting tier immediately
    """

    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can use this endpoint")

    # Check if already completed
    existing = employer_crud.get_employer_by_user_id(db, current_user.id)
    if existing and existing.profile_completed:
        raise HTTPException(status_code=400, detail="Registration already completed")

    # Validate email domain for REGISTERED companies (basic check, not verification)
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

        # ===== CRITICAL CHANGE: Start with UNVERIFIED tier =====
        employer.verification_tier = "UNVERIFIED"
        employer.trust_score = 20  # Very low until work email verified
        employer.work_email_verified = False

        db.commit()
        db.refresh(employer)

        # ===== NEW: Generate and send work email verification code =====
        code = create_work_email_verification_token(db, employer)
        send_work_email_verification(
            to_email=employer.work_email,
            code=code,
            company_name=employer.company_name
        )

        return employer

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ===== NEW: VERIFY WORK EMAIL =====

@router.post("/verify-work-email/confirm")
def confirm_work_email_verification(
    request: WorkEmailVerificationConfirm,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Verify work email with 6-digit code
    This ACTUALLY grants EMAIL_VERIFIED tier
    """
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can use this endpoint")

    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(status_code=404, detail="Employer profile not found")

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


# ===== NEW: RESEND WORK EMAIL VERIFICATION =====

@router.post("/verify-work-email/resend")
def resend_work_email_code(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Resend work email verification code
    Rate limited: 1 request per 2 minutes
    """
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can use this endpoint")

    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(status_code=404, detail="Employer profile not found")

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


# ===== NEW: CHECK WORK EMAIL VERIFICATION STATUS =====

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


@router.post("/profile/logo")
async def upload_logo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload company logo"""
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can upload logos")
    
    file_content = await validate_image_file(file)
    
    try:
        upload_result = cloudinary.uploader.upload(
            file_content,
            folder="jobscape/employer_logos",
            public_id=f"employer_{current_user.id}",
            overwrite=True,
            resource_type="image",
            transformation=[
                {"width": 400, "height": 400, "crop": "limit"},
                {"quality": "auto"}
            ]
        )
        logo_url = upload_result.get("secure_url")
        
        employer = employer_crud.update_employer_profile(
            db=db,
            user_id=current_user.id,
            logo_url=logo_url
        )
        return {"logo_url": logo_url, "message": "Logo uploaded successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


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
    """
    Submit company verification documents
    Upgrades to DOCUMENT_VERIFIED tier automatically
    """
    
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can request verification")
    
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(status_code=400, detail="Complete employer profile first")
    
    # Check if profile completed (if field exists)
    if hasattr(employer, 'profile_completed') and not employer.profile_completed:
        raise HTTPException(status_code=400, detail="Complete registration first")
    
    # Check if already fully verified
    if hasattr(employer, 'verification_tier') and employer.verification_tier == "FULLY_VERIFIED":
        raise HTTPException(status_code=400, detail="Already fully verified")
    
    # VALIDATION - Must provide at least one complete document set
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
    
    # UPLOAD DOCUMENTS
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
    
    # UPDATE EMPLOYER
    notes_parts = [f"Submitted: {datetime.now(timezone.utc).isoformat()}"]
    if linkedin_company_url:
        notes_parts.append(f"LinkedIn: {linkedin_company_url}")
    if additional_notes:
        notes_parts.append(f"Notes: {additional_notes}")
    
    # Get existing notes if field exists
    if hasattr(employer, 'verification_notes') and employer.verification_notes:
        notes_parts.append(f"\n--- Previous Notes ---\n{employer.verification_notes}")
    
    # Update fields (only if they exist)
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
        "message": "Documents submitted! Upgraded to DOCUMENT_VERIFIED. Admin will review for FULLY_VERIFIED status.",
        "verification_tier": getattr(employer, 'verification_tier', 'UNKNOWN'),
        "trust_score": getattr(employer, 'trust_score', 0),
        "documents_uploaded": len(uploaded_docs),
        "next_steps": "Wait for admin review to reach FULLY_VERIFIED status"
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
    
    # Safe attribute access
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

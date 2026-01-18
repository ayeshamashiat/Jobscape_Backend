from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone
from app.database import get_db
from app.schema.employer_schema import (
    EmployerRegistrationCreate,
    EmployerProfileUpdate,
    EmployerProfileResponse
)
from app.crud import employer_crud
from app.utils.security import get_current_user
from app.utils.file_validators import validate_image_file, validate_document_file
from app.utils.email_validators import verify_work_email_ownership
from app.utils.startup_verifier import verify_linkedin_company, verify_website_legitimacy, calculate_startup_trust_score
from app.models.user import User, UserRole
import cloudinary.uploader

router = APIRouter(prefix="/employer", tags=["employer"])


# ===== REGISTRATION COMPLETION =====

@router.post("/register/complete", response_model=EmployerProfileResponse, status_code=status.HTTP_201_CREATED)
def complete_employer_registration(
    profile_data: EmployerRegistrationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Complete employer registration after email verification"""
    
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can use this endpoint")
    
    # Check if already completed
    existing = employer_crud.get_employer_by_user_id(db, current_user.id)
    if existing and existing.profile_completed:
        raise HTTPException(status_code=400, detail="Registration already completed")
    
    # REGISTERED COMPANIES: Require email domain match
    if profile_data.company_type == "REGISTERED":
        if not profile_data.company_website:
            raise HTTPException(status_code=400, detail="Registered companies must provide website")
        
        is_valid, error_msg = verify_work_email_ownership(
            profile_data.work_email,
            profile_data.company_website
        )
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)
        
        initial_tier = "EMAIL_VERIFIED"
        trust_score = 60
        alt_verification = {}
    
    # STARTUPS: Alternative verification
    elif profile_data.company_type == "STARTUP":
        alt_verification = {}
        
        # Check LinkedIn if provided
        if profile_data.linkedin_url:
            linkedin_valid, linkedin_data = verify_linkedin_company(profile_data.linkedin_url)
            alt_verification["linkedin_url"] = profile_data.linkedin_url
            alt_verification["linkedin_valid"] = linkedin_valid
            alt_verification["linkedin_data"] = linkedin_data
        
        # Check website if provided
        if profile_data.company_website:
            website_checks = verify_website_legitimacy(profile_data.company_website)
            alt_verification["website_checks"] = website_checks
            alt_verification["website_has_ssl"] = website_checks.get("has_ssl", False)
        
        initial_tier = "EMAIL_VERIFIED" if alt_verification else "UNVERIFIED"
        trust_score = 40
    
    else:
        initial_tier = "UNVERIFIED"
        trust_score = 50
        alt_verification = {}
    
    # Create employer
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
        
        # Set company type fields
        employer.company_type = profile_data.company_type
        employer.is_startup = profile_data.is_startup
        employer.startup_stage = profile_data.startup_stage
        employer.founded_year = profile_data.founded_year
        employer.verification_tier = initial_tier
        employer.trust_score = trust_score
        employer.alternative_verification_data = alt_verification
        
        # Recalculate trust score for startups
        if profile_data.company_type == "STARTUP":
            employer.trust_score = calculate_startup_trust_score(employer)
        
        db.commit()
        db.refresh(employer)
        
        return employer
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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

@router.post("/verification/submit")
async def submit_verification_request(
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
    """Submit company verification request"""
    
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can request verification")
    
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(status_code=400, detail="Complete employer profile first")
    
    if not employer.profile_completed:
        raise HTTPException(status_code=400, detail="Complete registration first")
    
    if employer.verification_tier == "FULLY_VERIFIED":
        raise HTTPException(status_code=400, detail="Already verified")
    
    # VALIDATION
    has_valid_submission = (
        (rjsc_registration_number and incorporation_cert) or
        (trade_license_number and trade_license) or
        (tin_number and tin_certificate)
    )
    
    if not has_valid_submission:
        raise HTTPException(
            status_code=400,
            detail="Must provide at least ONE complete document set"
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
    if employer.verification_notes:
        notes_parts.append(f"\n--- Previous Notes ---\n{employer.verification_notes}")
    
    # Auto-upgrade to DOCUMENT_VERIFIED
    employer.verification_tier = "DOCUMENT_VERIFIED"
    employer.verification_documents = uploaded_docs
    employer.rjsc_registration_number = rjsc_registration_number
    employer.trade_license_number = trade_license_number
    employer.tin_number = tin_number
    employer.verification_notes = "\n".join(notes_parts)
    employer.trust_score += 15
    
    db.commit()
    db.refresh(employer)
    
    return {
        "message": "Documents verified! Upgraded to DOCUMENT_VERIFIED. Admin will review for FULLY_VERIFIED status.",
        "verification_tier": employer.verification_tier,
        "trust_score": employer.trust_score,
        "documents_uploaded": len(uploaded_docs),
        "next_steps": "Admin review for FULLY_VERIFIED status"
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
    
    return {
        "status": employer.verification_tier,
        "verified_at": employer.verified_at,
        "documents_submitted": len(employer.verification_documents),
        "trust_score": employer.trust_score,
        "can_submit": employer.verification_tier in ["UNVERIFIED", "EMAIL_VERIFIED", "REJECTED"]
    }

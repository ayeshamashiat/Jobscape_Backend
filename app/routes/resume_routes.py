from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.resume import Resume, ResumeParseStatus
from app.models.job_seeker import JobSeeker
from app.models.user import User, UserRole
from app.utils.security import get_current_user
from app.utils.file_validators import validate_resume_file  # ✅ Import from your existing util
from app.utils.text_extractor import extract_text_from_resume
from app.utils.cv_parser_ai import structure_resume_with_ai
import cloudinary.uploader
from datetime import datetime

router = APIRouter(prefix="/resume", tags=["resume"])


# ===================== CV UPLOAD =====================

@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # ✅ Normal auth (no temp token)
):
    """
    Upload CV to auto-populate job seeker profile
    
    New Flow (matches employer registration):
    1. User registers → Email sent immediately
    2. User verifies email → Can login
    3. User uploads CV (this endpoint) → Profile auto-populated
    4. User can browse/apply to jobs
    
    Requirements:
    - Must be logged in (email verified)
    - CV parsing failures are graceful (user can continue manually)
    """
    
    # ✅ Check role
    if current_user.role != UserRole.JOB_SEEKER:
        raise HTTPException(status_code=403, detail="Only job seekers can upload resumes")
    
    # ✅ Check email verification (REQUIRED before CV upload)
    if not current_user.is_email_verified:
        raise HTTPException(
            status_code=403,
            detail="Please verify your email before uploading your CV. Check your inbox for the verification link.",
            headers={"X-Next-Step": "email_verification"}
        )
    
    # Get job seeker profile
    job_seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not job_seeker:
        raise HTTPException(status_code=404, detail="Job seeker profile not found")
    
    # ✅ Validate file using your existing validator
    try:
        file_content = await validate_resume_file(file)
    except HTTPException:
        raise  # Re-raise validation errors as-is
    
    cloudinary_public_id = None
    
    try:
        # Mark previous resumes as not primary
        db.query(Resume).filter(Resume.job_seeker_id == job_seeker.id).update({"is_primary": False})
        db.commit()
        
        # ✅ Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            file_content,
            folder=f"jobscape/resumes/{current_user.id}",
            public_id=f"resume_{int(datetime.now().timestamp())}",
            resource_type="auto"  # Auto-detect PDF/DOC/DOCX
        )
        
        file_url = upload_result.get("secure_url")
        cloudinary_public_id = upload_result.get("public_id")
        
        # ✅ Create resume record with PENDING status first
        resume = Resume(
            job_seeker_id=job_seeker.id,
            file_url=file_url,
            cloudinary_public_id=cloudinary_public_id,
            parse_status=ResumeParseStatus.PENDING,
            is_primary=True
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)
        
        # ✅ Try to parse CV (graceful failure - user can continue even if this fails)
        parsing_successful = False
        parsing_error = None
        
        try:
            # Extract text from PDF/DOCX
            resume_text = extract_text_from_resume(file_content, file.filename)
            
            # Parse with AI
            parsed_data = structure_resume_with_ai(resume_text)
            
            # ✅ Update job seeker profile with parsed data
            if parsed_data:
                # Update only if data exists (don't override with None)
                if parsed_data.get("phone"):
                    job_seeker.phone = parsed_data["phone"]
                if parsed_data.get("location"):
                    job_seeker.location = parsed_data["location"]
                if parsed_data.get("professional_summary"):
                    job_seeker.professional_summary = parsed_data["professional_summary"]
                if parsed_data.get("skills"):
                    job_seeker.skills = parsed_data["skills"]
                if parsed_data.get("education"):
                    job_seeker.education = parsed_data["education"]
                if parsed_data.get("experience"):
                    job_seeker.experience = parsed_data["experience"]
                if parsed_data.get("projects"):
                    job_seeker.projects = parsed_data.get("projects", [])
                if parsed_data.get("certifications"):
                    job_seeker.certifications = parsed_data.get("certifications", [])
                if parsed_data.get("awards"):
                    job_seeker.awards = parsed_data.get("awards", [])
                if parsed_data.get("languages"):
                    job_seeker.languages = parsed_data.get("languages", [])
                if parsed_data.get("linkedin"):
                    job_seeker.linkedin_url = parsed_data["linkedin"]
                if parsed_data.get("github"):
                    job_seeker.github_url = parsed_data["github"]
                if parsed_data.get("portfolio"):
                    job_seeker.portfolio_url = parsed_data["portfolio"]
                
                # Mark profile as completed
                job_seeker.profile_completed = True
                parsing_successful = True
            
            # Update resume with parsed data
            resume.parsed_data = parsed_data
            resume.parse_status = ResumeParseStatus.SUCCESS
            
            db.commit()
            db.refresh(job_seeker)
            db.refresh(resume)
        
        except Exception as e:
            # ✅ GRACEFUL FAILURE: CV is uploaded but parsing failed
            print(f"⚠️ CV parsing failed for user {current_user.id}: {e}")
            parsing_error = str(e)
            
            resume.parse_status = ResumeParseStatus.FAILED
            db.commit()
        
        # ✅ Return success response (regardless of parsing outcome)
        if parsing_successful:
            return {
                "message": "CV uploaded and parsed successfully! Your profile has been auto-populated.",
                "resume_id": str(resume.id),
                "parse_status": "SUCCESS",
                "profile_completed": True,
                "extracted_data": {
                    "skills": (resume.parsed_data or {}).get("skills", [])[:5],  # Preview top 5
                    "experience_count": len((resume.parsed_data or {}).get("experience", [])),
                    "education_count": len((resume.parsed_data or {}).get("education", []))
                },
                "next_step": "browse_jobs"
            }
        else:
            return {
                "message": "CV uploaded successfully, but automatic parsing failed. You can manually complete your profile or try uploading again.",
                "resume_id": str(resume.id),
                "parse_status": "FAILED",
                "profile_completed": False,
                "next_step": "manual_profile_completion",
                "error": parsing_error,
                "can_retry": True,
                "instructions": "You can still browse and apply to jobs. Consider uploading a different CV format or complete your profile manually."
            }
    
    except HTTPException:
        raise
    except Exception as e:
        # ✅ Cleanup Cloudinary file if upload succeeded but DB failed
        db.rollback()
        if cloudinary_public_id:
            try:
                cloudinary.uploader.destroy(cloudinary_public_id, resource_type="auto")
            except Exception as cleanup_error:
                print(f"⚠️ Failed to cleanup Cloudinary file: {cleanup_error}")
        
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# ===================== UPDATE/REPLACE CV =====================

@router.put("/update")
async def update_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Replace existing CV with new one
    Same logic as initial upload
    """
    # Reuse the upload logic
    return await upload_resume(file, db, current_user)


# ===================== RETRY PARSING =====================

@router.post("/{resume_id}/retry-parse")
async def retry_resume_parsing(
    resume_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retry parsing a failed resume
    Useful if:
    - AI service was down during initial upload
    - Resume format was problematic but now fixed
    - User uploaded a new version
    """
    
    if current_user.role != UserRole.JOB_SEEKER:
        raise HTTPException(status_code=403, detail="Only job seekers can access this")
    
    job_seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not job_seeker:
        raise HTTPException(status_code=404, detail="Job seeker profile not found")
    
    # Get resume
    from uuid import UUID
    try:
        resume = db.query(Resume).filter(
            Resume.id == UUID(resume_id),
            Resume.job_seeker_id == job_seeker.id
        ).first()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid resume ID format")
    
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    if resume.parse_status == ResumeParseStatus.SUCCESS:
        raise HTTPException(
            status_code=400, 
            detail="Resume already parsed successfully. Upload a new CV if you want to update your profile."
        )
    
    try:
        # Download CV from Cloudinary
        import requests
        response = requests.get(resume.file_url)
        response.raise_for_status()
        file_content = response.content
        
        # Extract text
        filename = resume.file_url.split("/")[-1]
        resume_text = extract_text_from_resume(file_content, filename)
        
        # Parse with AI
        parsed_data = structure_resume_with_ai(resume_text)
        
        # Update profile
        if parsed_data:
            if parsed_data.get("phone"):
                job_seeker.phone = parsed_data["phone"]
            if parsed_data.get("location"):
                job_seeker.location = parsed_data["location"]
            if parsed_data.get("professional_summary"):
                job_seeker.professional_summary = parsed_data["professional_summary"]
            if parsed_data.get("skills"):
                job_seeker.skills = parsed_data["skills"]
            if parsed_data.get("education"):
                job_seeker.education = parsed_data["education"]
            if parsed_data.get("experience"):
                job_seeker.experience = parsed_data["experience"]
            if parsed_data.get("projects"):
                job_seeker.projects = parsed_data.get("projects", [])
            if parsed_data.get("certifications"):
                job_seeker.certifications = parsed_data.get("certifications", [])
            if parsed_data.get("linkedin"):
                job_seeker.linkedin_url = parsed_data["linkedin"]
            if parsed_data.get("github"):
                job_seeker.github_url = parsed_data["github"]
            
            job_seeker.profile_completed = True
        
        resume.parsed_data = parsed_data
        resume.parse_status = ResumeParseStatus.SUCCESS
        
        db.commit()
        db.refresh(job_seeker)
        
        return {
            "message": "Resume parsed successfully on retry!",
            "parse_status": "SUCCESS",
            "profile_completed": True,
            "extracted_data": {
                "skills": parsed_data.get("skills", [])[:5],
                "experience_count": len(parsed_data.get("experience", [])),
                "education_count": len(parsed_data.get("education", []))
            }
        }
    
    except Exception as e:
        resume.parse_status = ResumeParseStatus.FAILED
        db.commit()
        raise HTTPException(
            status_code=500, 
            detail=f"Parsing failed again: {str(e)}. Consider uploading a different CV format."
        )


# ===================== VIEW RESUMES =====================

@router.get("/my-resumes")
def get_my_resumes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all resumes uploaded by current user"""
    
    if current_user.role != UserRole.JOB_SEEKER:
        raise HTTPException(status_code=403, detail="Only job seekers can view resumes")
    
    job_seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not job_seeker:
        raise HTTPException(status_code=404, detail="Job seeker profile not found")
    
    resumes = db.query(Resume).filter(
        Resume.job_seeker_id == job_seeker.id
    ).order_by(Resume.uploaded_at.desc()).all()
    
    return {
        "resumes": resumes,
        "total": len(resumes),
        "primary_resume": next((r for r in resumes if r.is_primary), None)
    }


@router.get("/{resume_id}")
def get_resume_details(
    resume_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get specific resume details including parsed data"""
    
    if current_user.role != UserRole.JOB_SEEKER:
        raise HTTPException(status_code=403, detail="Only job seekers can access this")
    
    job_seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not job_seeker:
        raise HTTPException(status_code=404, detail="Job seeker profile not found")
    
    from uuid import UUID
    try:
        resume = db.query(Resume).filter(
            Resume.id == UUID(resume_id),
            Resume.job_seeker_id == job_seeker.id
        ).first()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid resume ID format")
    
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    return resume


@router.delete("/{resume_id}")
def delete_resume(
    resume_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a resume (removes from both Cloudinary and database)"""
    
    if current_user.role != UserRole.JOB_SEEKER:
        raise HTTPException(status_code=403, detail="Only job seekers can access this")
    
    job_seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not job_seeker:
        raise HTTPException(status_code=404, detail="Job seeker profile not found")
    
    from uuid import UUID
    try:
        resume = db.query(Resume).filter(
            Resume.id == UUID(resume_id),
            Resume.job_seeker_id == job_seeker.id
        ).first()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid resume ID format")
    
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    # Don't allow deleting the only resume if profile is completed based on it
    remaining_resumes = db.query(Resume).filter(
        Resume.job_seeker_id == job_seeker.id,
        Resume.id != resume.id
    ).count()
    
    if remaining_resumes == 0 and job_seeker.profile_completed:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete your only resume. Upload a new one first or your profile will be incomplete."
        )
    
    # Delete from Cloudinary
    if resume.cloudinary_public_id:
        try:
            cloudinary.uploader.destroy(resume.cloudinary_public_id, resource_type="auto")
        except Exception as e:
            print(f"⚠️ Failed to delete from Cloudinary: {e}")
            # Continue anyway - DB deletion is more important
    
    # Delete from DB
    db.delete(resume)
    db.commit()
    
    return {"message": "Resume deleted successfully"}

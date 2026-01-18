from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.resume import Resume, ResumeParseStatus
from app.models.job_seeker import JobSeeker
from app.utils.security import get_current_user
from app.utils.email import send_verification_email
from app.utils.text_extractor import extract_text_from_resume
from app.utils.cv_parser_ai import structure_resume_with_ai
from app.utils.file_validators import validate_resume_file
from app.models.user import User, UserRole
import cloudinary.uploader
from datetime import datetime 
from app.utils.security import get_current_user_allow_inactive 

router = APIRouter(prefix="/resume", tags=["resume"])

@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_allow_inactive)  # ← Use this instead
):
    """
    Step 2: Upload CV (MANDATORY after basic registration).
    This completes the registration and triggers email verification.
    """
    
    if current_user.role != UserRole.JOB_SEEKER:
        raise HTTPException(status_code=403, detail="Only job seekers can upload resumes")
    
    # Get job seeker profile
    job_seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not job_seeker:
        raise HTTPException(status_code=400, detail="Job seeker profile not found")
    
    # Check if already completed
    if current_user.is_active and job_seeker.profile_completed:
        raise HTTPException(
            status_code=400, 
            detail="Registration already completed. Use /resume/update to update your CV."
        )
    
    # Validate and upload CV
    file_content = await validate_resume_file(file)
    
    cloudinary_public_id = None
    
    try:
        # Mark previous resumes as not primary
        db.query(Resume).filter(Resume.job_seeker_id == job_seeker.id).update({"is_primary": False})
        
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            file_content,
            folder="jobscape/resumes",
            public_id=f"resume_{job_seeker.id}_{int(datetime.now().timestamp())}",
            resource_type="raw"
        )
        
        file_url = upload_result.get("secure_url")
        cloudinary_public_id = upload_result.get("public_id")
        
        # Extract and parse CV
        resume_text = extract_text_from_resume(file_content, file.filename)
        parsed_data = structure_resume_with_ai(resume_text)
        
        # ✅ VERIFY EMAIL MATCH (Optional - see previous discussion)
        cv_email = parsed_data.get("email", "").strip().lower() if parsed_data else None
        registration_email = current_user.email.strip().lower()
        
        if cv_email and cv_email != registration_email:
            # Just log warning, don't block
            print(f"⚠️ Warning: CV email ({cv_email}) != registration email ({registration_email})")
        
        # ✅ UPDATE JOB SEEKER PROFILE
        if parsed_data:
            # Don't override full_name from registration
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
                job_seeker.projects = parsed_data["projects"]
            if parsed_data.get("certifications"):
                job_seeker.certifications = parsed_data["certifications"]
            if parsed_data.get("linkedin"):
                job_seeker.linkedin_url = parsed_data["linkedin"]
            if parsed_data.get("github"):
                job_seeker.github_url = parsed_data["github"]
            
            job_seeker.profile_completed = True
        
        # ✅ ACTIVATE USER ACCOUNT
        current_user.is_active = True
        
        db.commit()
        db.refresh(job_seeker)
        db.refresh(current_user)
        
        # Save resume record
        resume = Resume(
            job_seeker_id=job_seeker.id,
            file_url=file_url,
            cloudinary_public_id=cloudinary_public_id,
            parsed_data=parsed_data,
            parse_status=ResumeParseStatus.SUCCESS,
            is_primary=True
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)
        
        # ✅ GET EMAIL VERIFICATION TOKEN
        from app.crud.auth_crud import create_email_verification_token
        from app.utils.email import send_verification_email
        
        token = create_email_verification_token(db, current_user)
        
        # Send verification email
        try:
            send_verification_email(current_user.email, token)
        except Exception as e:
            print(f"⚠️ Failed to send verification email: {e}")
        
        return {
            "message": "CV uploaded successfully! Your profile is now complete. Please verify your email.",
            "resume_id": str(resume.id),
            "profile_completed": True,
            "email_verification_sent": True,
            "next_step": "Check your email to verify your account"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        if cloudinary_public_id:
            try:
                cloudinary.uploader.destroy(cloudinary_public_id, resource_type="raw")
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/my-resumes")
def get_my_resumes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.JOB_SEEKER:
        raise HTTPException(status_code=403, detail="Only job seekers can view resumes")
    
    job_seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not job_seeker:
        raise HTTPException(status_code=400, detail="Job seeker profile not found")
    
    resumes = db.query(Resume).filter(
        Resume.job_seeker_id == job_seeker.id
    ).order_by(Resume.uploaded_at.desc()).all()
    
    return resumes

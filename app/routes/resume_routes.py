from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.resume import Resume, ResumeParseStatus
from app.models.job_seeker import JobSeeker
from app.utils.security import get_current_user
from app.utils.text_extractor import extract_text_from_resume
from app.utils.cv_parser_ai import structure_resume_with_ai
from app.utils.file_validators import validate_resume_file
from app.models.user import User, UserRole
import cloudinary.uploader
from datetime import datetime 

router = APIRouter(prefix="/resume", tags=["resume"])

@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.JOB_SEEKER:
        raise HTTPException(status_code=403, detail="Only job seekers can upload resumes")
    
    # Get job seeker profile
    job_seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not job_seeker:
        raise HTTPException(status_code=400, detail="Complete job seeker profile first")
    
    # Validate file
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
        
        # Extract text
        try:
            resume_text = extract_text_from_resume(file_content, file.filename)
        except ValueError as e:
            # Text extraction failed
            resume = Resume(
                job_seeker_id=job_seeker.id,
                file_url=file_url,
                cloudinary_public_id=cloudinary_public_id,
                parsed_data={"error": str(e)},
                parse_status=ResumeParseStatus.FAILED,
                is_primary=True
            )
            db.add(resume)
            db.commit()
            db.refresh(resume)
            raise HTTPException(status_code=400, detail=f"Failed to extract text: {str(e)}")
        
        # Parse with AI
        parsed_data = None
        parse_status = ResumeParseStatus.PENDING
        
        try:
            parsed_data = structure_resume_with_ai(resume_text)
            parse_status = ResumeParseStatus.SUCCESS
        except Exception as parse_error:
            print(f"AI parsing failed: {parse_error}")
            parsed_data = {"raw_text": resume_text[:1000]}  # Store first 1000 chars
            parse_status = ResumeParseStatus.FAILED
        
        # Save to database
        resume = Resume(
            job_seeker_id=job_seeker.id,
            file_url=file_url,
            cloudinary_public_id=cloudinary_public_id,
            parsed_data=parsed_data,
            parse_status=parse_status,
            is_primary=True
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)
        
        return {
            "resume_id": str(resume.id),
            "file_url": file_url,
            "parsed_data": parsed_data,
            "parse_status": parse_status
        }
    
    except HTTPException:
        raise
    except Exception as e:
        # Rollback database
        db.rollback()
        
        # Delete from Cloudinary if uploaded
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

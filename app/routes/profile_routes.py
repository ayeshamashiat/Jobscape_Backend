# app/routes/profile_routes.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.security import get_current_user
from app.models.user import User, UserRole
from app.models.job_seeker import JobSeeker
from app.models.employer import Employer
from app.utils.file_validators import validate_image_file
import cloudinary.uploader
from typing import Dict
from app.schema.job_seeker_schema import JobSeekerProfileUpdate, JobSeekerProfileResponse

router = APIRouter(prefix="/profile", tags=["profile"])


@router.post("/profile-picture/upload")
async def upload_profile_picture(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Upload profile picture for both job seekers and employers.
    Automatically handles based on user role.
    """
    # Validate image file (AWAIT IT)
    await validate_image_file(file)
    
    # Reset file pointer after validation
    await file.seek(0)
    
    try:
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            file.file,
            folder=f"profile_pictures/{current_user.role.value}",
            public_id=f"{current_user.id}",
            overwrite=True,
            resource_type="image",
            transformation=[
                {"width": 400, "height": 400, "crop": "fill", "gravity": "face"},
                {"quality": "auto"},
                {"fetch_format": "auto"}
            ]
        )
        
        image_url = upload_result.get("secure_url")
        cloudinary_public_id = upload_result.get("public_id")
        
        # Update based on role
        if current_user.role == UserRole.JOB_SEEKER:
            jobseeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
            if not jobseeker:
                raise HTTPException(status_code=404, detail="Job seeker profile not found")
            
            # Delete old image if exists
            if jobseeker.profile_picture_url:
                # Extract public_id from the stored field or construct it
                old_public_id = getattr(jobseeker, 'cloudinary_public_id', None)
                if old_public_id:
                    try:
                        cloudinary.uploader.destroy(old_public_id)
                    except:
                        pass  # Ignore if deletion fails
            
            jobseeker.profile_picture_url = image_url
            # Only set this if you added the field to the model
            if hasattr(jobseeker, 'cloudinary_public_id'):
                jobseeker.cloudinary_public_id = cloudinary_public_id
            
        elif current_user.role == UserRole.EMPLOYER:
            employer = db.query(Employer).filter(Employer.user_id == current_user.id).first()
            if not employer:
                raise HTTPException(status_code=404, detail="Employer profile not found")
            
            # Delete old image if exists
            if employer.logo_url:
                old_public_id = getattr(employer, 'cloudinary_public_id', None)
                if old_public_id:
                    try:
                        cloudinary.uploader.destroy(old_public_id)
                    except:
                        pass
            
            employer.logo_url = image_url
            # Only set this if you added the field to the model
            if hasattr(employer, 'cloudinary_public_id'):
                employer.cloudinary_public_id = cloudinary_public_id
        
        else:
            raise HTTPException(status_code=403, detail="Admins cannot upload profile pictures")
        
        db.commit()
        
        return {
            "message": "Profile picture uploaded successfully",
            "url": image_url
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload image: {str(e)}"
        )


@router.delete("/profile-picture")
async def remove_profile_picture(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Remove profile picture for both job seekers and employers.
    Automatically handles based on user role.
    """
    try:
        if current_user.role == UserRole.JOBSEEKER:
            jobseeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
            if not jobseeker:
                raise HTTPException(status_code=404, detail="Job seeker profile not found")
            
            # Delete from Cloudinary
            if hasattr(jobseeker, 'cloudinary_public_id') and jobseeker.cloudinary_public_id:
                try:
                    cloudinary.uploader.destroy(jobseeker.cloudinary_public_id)
                except:
                    pass  # Ignore if deletion fails
            
            jobseeker.profile_picture_url = None
            if hasattr(jobseeker, 'cloudinary_public_id'):
                jobseeker.cloudinary_public_id = None
            
        elif current_user.role == UserRole.EMPLOYER:
            employer = db.query(Employer).filter(Employer.user_id == current_user.id).first()
            if not employer:
                raise HTTPException(status_code=404, detail="Employer profile not found")
            
            # Delete from Cloudinary
            if hasattr(employer, 'cloudinary_public_id') and employer.cloudinary_public_id:
                try:
                    cloudinary.uploader.destroy(employer.cloudinary_public_id)
                except:
                    pass
            
            employer.logo_url = None
            if hasattr(employer, 'cloudinary_public_id'):
                employer.cloudinary_public_id = None
        
        else:
            raise HTTPException(status_code=403, detail="Admins do not have profile pictures")
        
        db.commit()
        
        return {
            "message": "Profile picture removed successfully"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove image: {str(e)}"
        )


@router.patch("/profile-picture/change")
async def change_profile_picture(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Change profile picture (removes old, uploads new).
    This is just a convenience wrapper around upload (which already handles replacement).
    """
    return await upload_profile_picture(file, db, current_user)

@router.patch("/profile", response_model=JobSeekerProfileResponse)
def update_profile(
    data: JobSeekerProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update job seeker profile - supports partial updates"""
    
    # Verify user is a job seeker
    if current_user.role != UserRole.JOB_SEEKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only job seekers can update profile"
        )
    
    # Get job seeker profile
    jobseeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not jobseeker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job seeker profile not found"
        )
    
    # Update only the fields that were sent (exclude_unset=True)
    update_data = data.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        if hasattr(jobseeker, field):
            setattr(jobseeker, field, value)
    
    # Auto-check if profile is complete
    required_fields_filled = all([
        jobseeker.full_name,
        jobseeker.phone,
        jobseeker.location,
        jobseeker.professional_summary,
        jobseeker.skills and len(jobseeker.skills) > 0,
    ])
    
    jobseeker.profile_completed = required_fields_filled
    
    db.commit()
    db.refresh(jobseeker)
    
    return jobseeker
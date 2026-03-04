# app/routes/coverletter_routes.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.utils.security import get_current_user
from app.models.user import User, UserRole
from app.models.job_seeker import JobSeeker
from app.models.cover_letter import SavedCoverLetter
from app.schema.cover_letter_schema import (
    CoverLetterCreate,
    CoverLetterResponse,
    CoverLetterUpdate
)
import uuid
from app.utils.ai_cover_letter_generator import generate_cover_letter, CoverLetterGeneratorError
from app.models.job import Job
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/jobseeker/cover-letters", tags=["cover-letters"])


@router.post("/", response_model=CoverLetterResponse, status_code=status.HTTP_201_CREATED)
def create_cover_letter(
    data: CoverLetterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new cover letter for the authenticated job seeker"""
    
    # Verify user is a job seeker
    if current_user.role != UserRole.JOB_SEEKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only job seekers can create cover letters"
        )
    
    # Get job seeker profile
    jobseeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not jobseeker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job seeker profile not found"
        )
    
    # Create cover letter
    cover_letter = SavedCoverLetter(
        jobseeker_id=jobseeker.id,
        title=data.title,
        content=data.content
    )
    
    db.add(cover_letter)
    db.commit()
    db.refresh(cover_letter)
    
    return cover_letter


@router.get("/", response_model=List[CoverLetterResponse])
def get_my_cover_letters(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all cover letters for the authenticated job seeker"""
    
    # Verify user is a job seeker
    if current_user.role != UserRole.JOB_SEEKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only job seekers can view cover letters"
        )
    
    # Get job seeker profile
    jobseeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not jobseeker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job seeker profile not found"
        )
    
    # Get all cover letters for this job seeker
    cover_letters = db.query(SavedCoverLetter)\
        .filter(SavedCoverLetter.jobseeker_id == jobseeker.id)\
        .order_by(SavedCoverLetter.updated_at.desc())\
        .all()
    
    return cover_letters


@router.get("/{id}", response_model=CoverLetterResponse)
def get_cover_letter(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific cover letter by ID"""
    
    # Verify user is a job seeker
    if current_user.role != UserRole.JOBSEEKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only job seekers can view cover letters"
        )
    
    # Get job seeker profile
    jobseeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not jobseeker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job seeker profile not found"
        )
    
    # Get cover letter
    cover_letter = db.query(SavedCoverLetter)\
        .filter(
            SavedCoverLetter.id == id,
            SavedCoverLetter.jobseeker_id == jobseeker.id
        )\
        .first()
    
    if not cover_letter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cover letter not found"
        )
    
    return cover_letter


@router.patch("/{id}", response_model=CoverLetterResponse)
def update_cover_letter(
    id: uuid.UUID,
    data: CoverLetterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a cover letter"""
    
    # Verify user is a job seeker
    if current_user.role != UserRole.JOBSEEKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only job seekers can update cover letters"
        )
    
    # Get job seeker profile
    jobseeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not jobseeker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job seeker profile not found"
        )
    
    # Get cover letter
    cover_letter = db.query(SavedCoverLetter)\
        .filter(
            SavedCoverLetter.id == id,
            SavedCoverLetter.jobseeker_id == jobseeker.id
        )\
        .first()
    
    if not cover_letter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cover letter not found"
        )
    
    # Update fields if provided
    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(cover_letter, field, value)
    
    db.commit()
    db.refresh(cover_letter)
    
    return cover_letter


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cover_letter(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a cover letter"""
    
    # Verify user is a job seeker
    if current_user.role != UserRole.JOBSEEKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only job seekers can delete cover letters"
        )
    
    # Get job seeker profile
    jobseeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not jobseeker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job seeker profile not found"
        )
    
    # Get cover letter
    cover_letter = db.query(SavedCoverLetter)\
        .filter(
            SavedCoverLetter.id == id,
            SavedCoverLetter.jobseeker_id == jobseeker.id
        )\
        .first()
    
    if not cover_letter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cover letter not found"
        )
    
    db.delete(cover_letter)
    db.commit()
    
    return None

@router.post("/generate", status_code=status.HTTP_200_OK)
def generate_ai_cover_letter(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate AI cover letter for a specific job
    
    Uses job details + user profile to create personalized cover letter
    Does NOT save automatically - user can choose to save after review
    """
    
    if current_user.role != UserRole.JOB_SEEKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only job seekers can generate cover letters"
        )
    
    # Get job seeker profile
    job_seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not job_seeker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job seeker profile not found"
        )
    
    # Get job details
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Build user profile dict
    user_profile = {
        "full_name": job_seeker.full_name,
        "skills": job_seeker.skills or [],
        "experience": job_seeker.experience or [],
        "education": job_seeker.education or [],
        "professional_summary": job_seeker.professional_summary,
        "location": job_seeker.location
    }
    
    # Check if profile has minimum data
    if not user_profile["full_name"]:
        raise HTTPException(
            status_code=400,
            detail="Please complete your profile (at least name and skills) before generating cover letters"
        )
    
    try:
        # Generate cover letter using AI utility
        cover_letter_text = generate_cover_letter(
            job_title=job.title,
            company_name=None,  # We don't expose company name in public job listings
            job_location=job.location,
            required_skills=job.required_skills or [],
            experience_level=job.experience_level,
            job_type=job.job_type,
            work_mode=job.work_mode,
            user_profile=user_profile,
            provider="groq"  # Can make this configurable
        )
        
        return {
            "cover_letter": cover_letter_text,
            "job_title": job.title,
            "generated_at": datetime.now().isoformat(),
            "word_count": len(cover_letter_text.split()),
            "char_count": len(cover_letter_text),
            "message": "Cover letter generated successfully. Review and edit before using."
        }
    
    except CoverLetterGeneratorError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate cover letter: {str(e)}"
        )

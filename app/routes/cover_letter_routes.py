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


router = APIRouter(prefix="/jobseeker/cover-letters", tags=["cover-letters"])


@router.post("/", response_model=CoverLetterResponse, status_code=status.HTTP_201_CREATED)
def create_cover_letter(
    data: CoverLetterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new cover letter for the authenticated job seeker"""
    
    # Verify user is a job seeker
    if current_user.role != UserRole.JOBSEEKER:
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

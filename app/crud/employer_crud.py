from sqlalchemy.orm import Session
from app.models.employer import Employer
from uuid import UUID
from typing import Optional


def create_or_update_employer_registration(
    db: Session,
    user_id: UUID,
    full_name: str,
    job_title: str,
    work_email: str,
    company_name: str,
    industry: str,
    location: str,
    company_website: Optional[str] = None,
    company_size: Optional[str] = None,
    description: Optional[str] = None
) -> Employer:
    """Create or update employer profile during registration"""
    
    # Check if employer already exists
    employer = db.query(Employer).filter(Employer.user_id == user_id).first()
    
    if employer:
        # Update existing
        employer.full_name = full_name
        employer.job_title = job_title
        employer.work_email = work_email
        employer.company_name = company_name
        employer.company_website = company_website
        employer.industry = industry
        employer.location = location
        employer.company_size = company_size
        employer.description = description
        employer.profile_completed = True
    else:
        # Create new
        employer = Employer(
            user_id=user_id,
            full_name=full_name,
            job_title=job_title,
            work_email=work_email,
            company_name=company_name,
            company_email=work_email,  # Default to work email
            company_website=company_website,
            industry=industry,
            location=location,
            company_size=company_size,
            description=description,
            profile_completed=True
        )
        db.add(employer)
    
    db.commit()
    db.refresh(employer)
    return employer


def get_employer_by_user_id(db: Session, user_id: UUID) -> Optional[Employer]:
    """Get employer by user ID"""
    return db.query(Employer).filter(Employer.user_id == user_id).first()


def get_employer_by_id(db: Session, employer_id: UUID) -> Optional[Employer]:
    """Get employer by ID"""
    return db.query(Employer).filter(Employer.id == employer_id).first()


def update_employer_profile(
    db: Session,
    user_id: UUID,
    **kwargs
) -> Employer:
    """Update employer profile"""
    employer = get_employer_by_user_id(db, user_id)
    if not employer:
        raise ValueError("Employer profile not found")
    
    for key, value in kwargs.items():
        if value is not None and hasattr(employer, key):
            setattr(employer, key, value)
    
    db.commit()
    db.refresh(employer)
    return employer


def check_duplicate_company(
    db: Session,
    company_name: str,
    rjsc_number: Optional[str] = None,
    exclude_employer_id: Optional[UUID] = None
) -> Optional[Employer]:
    """Check for duplicate company registration"""
    query = db.query(Employer).filter(Employer.company_name == company_name)
    
    if rjsc_number:
        query = query.filter(Employer.rjsc_registration_number == rjsc_number)
    
    if exclude_employer_id:
        query = query.filter(Employer.id != exclude_employer_id)
    
    return query.first()

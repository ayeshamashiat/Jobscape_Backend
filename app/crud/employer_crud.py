from sqlalchemy.orm import Session
from app.models.employer import Employer
from app.models.user import User
import uuid

def create_employer_profile(
    db: Session, 
    user_id: uuid.UUID, 
    company_name: str,
    company_email: str,
    location: str = None,
    website: str = None,
    industry: str = None,
    size: str = None,
    description: str = None,
    logo_url: str = None
) -> Employer:
    # Check if employer profile already exists
    existing = db.query(Employer).filter(Employer.user_id == user_id).first()
    if existing:
        raise ValueError("Employer profile already exists")
    
    employer = Employer(
        user_id=user_id,
        company_name=company_name,
        company_email=company_email,
        location=location,
        website=website,
        industry=industry,
        size=size,
        description=description,
        logo_url=logo_url
    )
    db.add(employer)
    db.commit()
    db.refresh(employer)
    return employer

def get_employer_by_user_id(db: Session, user_id: uuid.UUID) -> Employer:
    return db.query(Employer).filter(Employer.user_id == user_id).first()

def update_employer_profile(db: Session, user_id: uuid.UUID, **kwargs) -> Employer:
    employer = get_employer_by_user_id(db, user_id)
    if not employer:
        raise ValueError("Employer profile not found")
    
    for key, value in kwargs.items():
        if hasattr(employer, key) and value is not None:
            setattr(employer, key, value)
    
    db.commit()
    db.refresh(employer)
    return employer

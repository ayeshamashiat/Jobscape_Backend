from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from app.database import get_db
from app.schema.employer_schema import (
    EmployerProfileCreate, 
    EmployerProfileUpdate, 
    EmployerProfileResponse
)
from app.crud import employer_crud
from app.utils.security import get_current_user
from app.utils.file_validators import validate_image_file
from app.models.user import User, UserRole
import cloudinary.uploader

router = APIRouter(prefix="/employer", tags=["employer"])

@router.post("/profile", response_model=EmployerProfileResponse, status_code=status.HTTP_201_CREATED)
def create_employer_profile(
    profile_data: EmployerProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can create employer profiles")
    
    try:
        employer = employer_crud.create_employer_profile(
            db=db,
            user_id=current_user.id,
            **profile_data.dict()
        )
        return employer
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/profile/me", response_model=EmployerProfileResponse)
def get_my_employer_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can upload logos")
    
    # Validate image file
    file_content = await validate_image_file(file)
    
    try:
        upload_result = cloudinary.uploader.upload(
            file_content,
            folder="jobscape/employer_logos",
            public_id=f"employer_{current_user.id}",
            overwrite=True,
            resource_type="image"
        )
        logo_url = upload_result.get("secure_url")
        
        # Update employer profile
        employer = employer_crud.update_employer_profile(
            db=db,
            user_id=current_user.id,
            logo_url=logo_url
        )
        return {"logo_url": logo_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm

from app.database import get_db
from app.crud import user_crud
from app.schema.user_schema import UserCreate, UserResponse, Token
from app.models.user import UserRole
from app.utils.security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

# --------------------------
# Job Seeker Registration
# --------------------------
@router.post("/register/job-seeker", response_model=UserResponse)
def register_job_seeker(user_in: UserCreate, db: Session = Depends(get_db)):
    if not user_in.password:
        raise HTTPException(status_code=400, detail="Password required")
    
    try:
        user = user_crud.create_job_seeker(
            db, 
            email=user_in.email, 
            password=user_in.password  # now guaranteed str
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return user


# --------------------------
# Employer / Job Poster Registration
# --------------------------
@router.post("/register/employer", response_model=UserResponse)
def register_employer(user_in: UserCreate, db: Session = Depends(get_db)):
    if not user_in.password:
        raise HTTPException(status_code=400, detail="Password required")
    
    try:
        user = user_crud.create_employer(
            db, 
            email=user_in.email, 
            password=user_in.password  # now guaranteed str
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return user

# --------------------------
# Login
# --------------------------
@router.post("/login", response_model=Token)
def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = user_crud.authenticate_user(db, form_data.username, form_data.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return {"access_token": token, "token_type": "bearer"}

# --------------------------
# OAuth Login
# --------------------------
@router.post("/oauth", response_model=Token)
def oauth_login(email: str, db: Session = Depends(get_db)):
    user = user_crud.get_user_by_email(db, email)
    if user is None:
        # By default, OAuth users are job seekers
        user = user_crud.create_user(db, email=email, role=UserRole.JOB_SEEKER)

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return {"access_token": token, "token_type": "bearer"}

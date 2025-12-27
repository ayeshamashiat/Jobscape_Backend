from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm

from app.database import get_db
from app.crud import user_crud
from app.crud import auth_crud
from app.crud.auth_crud import set_email_verified, create_password_reset_token
from app.schema.user_schema import UserCreate, UserResponse
from app.schema.auth_schema import Token
from app.schema.email_schema import EmailVerificationConfirm, EmailVerificationRequest
from app.schema.password_schema import PasswordResetRequest, PasswordResetConfirm
from app.utils.security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

# --------------------------
# Registration
# --------------------------
@router.post("/register/job-seeker", response_model=UserResponse)
def register_job_seeker(user_in: UserCreate, db: Session = Depends(get_db)):
    if not user_in.password:
        raise HTTPException(status_code=400, detail="Password required")
    try:
        user = user_crud.create_job_seeker(db, email=user_in.email, password=user_in.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return user

@router.post("/register/employer", response_model=UserResponse)
def register_employer(user_in: UserCreate, db: Session = Depends(get_db)):
    if not user_in.password:
        raise HTTPException(status_code=400, detail="Password required")
    try:
        user = user_crud.create_employer(db, email=user_in.email, password=user_in.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return user

# --------------------------
# Login
# --------------------------
@router.post("/login", response_model=Token)
def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = user_crud.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return {"access_token": token, "token_type": "bearer"}

# --------------------------
# OAuth Login
# --------------------------
@router.post("/oauth", response_model=Token)
def oauth_login(email: str, db: Session = Depends(get_db)):
    user = user_crud.get_user_by_email(db, email)
    if not user:
        user = user_crud.create_user(db, email=email, role=user_crud.UserRole.JOB_SEEKER)
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return {"access_token": token, "token_type": "bearer"}

# --------------------------
# Email Verification
# --------------------------
@router.post("/verify-email", response_model=UserResponse)
def verify_email(data: EmailVerificationConfirm, db: Session = Depends(get_db)):
    user = db.query(user_crud.User).filter_by(email_verification_token=data.token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid token")
    auth_crud.set_email_verified(db, user)
    return user

# --------------------------
# Password Reset
# --------------------------
@router.post("/forgot-password")
def forgot_password(data: PasswordResetRequest, db: Session = Depends(get_db)):
    user = user_crud.get_user_by_email(db, data.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    token = auth_crud.create_password_reset_token(db, user)
    # send token via email here
    return {"message": "Password reset token sent"}

@router.post("/reset-password")
def reset_password(data: PasswordResetConfirm, db: Session = Depends(get_db)):
    try:
        user = auth_crud.reset_password(db, token=data.token, new_password=data.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "Password updated successfully"}

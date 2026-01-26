from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from app.database import get_db
from app.crud import user_crud
from app.crud import auth_crud
from app.crud.auth_crud import verify_email, create_email_verification_token, create_password_reset_token, reset_password
from app.schema.user_schema import UserCreate, UserResponse, JobSeekerBasicRegistration
from app.schema.auth_schema import Token
from app.schema.email_schema import EmailVerificationConfirm, EmailVerificationRequest
from app.schema.password_schema import PasswordResetRequest, PasswordResetConfirm
from app.utils.security import create_access_token, get_current_user, verify_password, hash_password
from app.utils.email import send_verification_email, send_password_reset_email
from app.models.user import User, UserRole
from app.models.job_seeker import JobSeeker
from app.models.employer import Employer
from datetime import timedelta
from collections import defaultdict
from datetime import datetime
from app.utils.security import oauth2_scheme


router = APIRouter(
    prefix="/auth",
    tags=["authentication"]
)

# ===================== RATE LIMITING =====================
_rate_limit_store = defaultdict(list)

def check_rate_limit(email: str, max_attempts: int = 5, window_minutes: int = 60):
    """Prevent registration spam"""
    now = datetime.now()
    cutoff = now - timedelta(minutes=window_minutes)
    
    _rate_limit_store[email] = [
        attempt for attempt in _rate_limit_store[email]
        if attempt > cutoff
    ]
    
    if len(_rate_limit_store[email]) >= max_attempts:
        raise HTTPException(
            status_code=429,
            detail=f"Too many registration attempts. Please try again in {window_minutes} minutes.",
            headers={"Retry-After": str(window_minutes * 60)}
        )
    
    _rate_limit_store[email].append(now)


# ===================== REGISTRATION =====================

@router.post("/register/job-seeker/basic", status_code=status.HTTP_201_CREATED, tags=["public"])
def register_job_seeker(user: JobSeekerBasicRegistration, db: Session = Depends(get_db)):
    """Job Seeker Registration"""
    check_rate_limit(user.email)
    
    existing_user = user_crud.get_user_by_email(db, user.email)
    if existing_user:
        if not existing_user.is_email_verified:
            token = create_email_verification_token(db, existing_user)
            send_verification_email(existing_user.email, token)
            return {
                "message": "Account already exists but email is not verified. We've resent the verification email.",
                "email": existing_user.email,
                "next_step": "email_verification"
            }
        else:
            raise HTTPException(
                status_code=400,
                detail="Email already registered. Please login or reset your password.",
                headers={"X-Registration-Status": "EMAIL_EXISTS"}
            )
    
    new_user = User(
        email=user.email,
        hashed_password=hash_password(user.password),
        role=UserRole.JOB_SEEKER,
        is_active=True,
        is_email_verified=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    job_seeker = JobSeeker(
        user_id=new_user.id,
        full_name=user.full_name,
        profile_completed=False
    )
    db.add(job_seeker)
    db.commit()
    
    token = create_email_verification_token(db, new_user)
    send_verification_email(new_user.email, token)
    
    return {
        "message": "Registration successful! Please check your email to verify your account.",
        "user_id": str(new_user.id),
        "email": new_user.email,
        "next_step": "email_verification"
    }


@router.post("/register/employer", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["public"])
def register_employer(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new employer account"""
    existing_user = user_crud.get_user_by_email(db, user.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    new_user = user_crud.create_user(db, user.email, UserRole.EMPLOYER, user.password)
    
    employer = Employer(
        user_id=new_user.id,
        company_name=user.full_name,
        company_email=user.email,
        profile_completed=False
    )
    db.add(employer)
    db.commit()
    db.refresh(employer)
    
    token = create_email_verification_token(db, new_user)
    send_verification_email(new_user.email, token)
    
    return new_user


# ===================== LOGIN =====================
@router.post("/login", response_model=Token, tags=["public"])
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Login with email and password"""
    user = user_crud.get_user_by_email(db, form_data.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No password set for this account"
        )
    
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please check your inbox.",
            headers={
                "X-Next-Step": "email_verification",
                "X-User-Email": user.email
            }
        )
    
    access_token = create_access_token(
        data={"sub": str(user.id)}, 
        expires_delta=timedelta(minutes=60 * 24)
    )
    
    extra_data = {}
    if user.role == UserRole.JOB_SEEKER:
        jobseeker = db.query(JobSeeker).filter(JobSeeker.user_id == user.id).first()
        if jobseeker:
            extra_data["profile_completed"] = jobseeker.profile_completed
            extra_data["next_step"] = "upload_cv" if not jobseeker.profile_completed else "browse_jobs"
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        **extra_data
    }


# ===================== EMAIL VERIFICATION =====================

@router.post("/verify-email/request", tags=["public"])
def request_email_verification(request: EmailVerificationRequest, db: Session = Depends(get_db)):
    """Request a new email verification token"""
    user = user_crud.get_user_by_email(db, request.email)
    
    if not user:
        return {"message": "If email exists, verification link has been sent"}
    
    if user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified"
        )
    
    token = create_email_verification_token(db, user)
    send_verification_email(user.email, token)
    
    return {"message": "Verification email sent"}


@router.post("/verify-email/confirm", tags=["public"])
def confirm_email_verification(request: EmailVerificationConfirm, db: Session = Depends(get_db)):
    """Verify email using the token sent via email"""
    try:
        user = verify_email(db, request.token)
        cv_upload_token = create_access_token(
            data={"sub": str(user.id), "scope": "cv_upload"},
            expires_delta=timedelta(minutes=15)
        )

        return {
            "message": "Email verified successfully",
            "email": user.email,
            "cv_upload_token": cv_upload_token
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ===================== PASSWORD RESET =====================

@router.post("/password-reset/request", tags=["public"])
def request_password_reset(request: PasswordResetRequest, db: Session = Depends(get_db)):
    """Request a password reset token"""
    user = user_crud.get_user_by_email(db, request.email)
    
    if not user:
        return {"message": "If email exists, password reset link has been sent"}
    
    try:
        token = create_password_reset_token(db, user)
        send_password_reset_email(user.email, token)
        
        return {"message": "Password reset link sent to email"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/password-reset/confirm", tags=["public"])
def confirm_password_reset(request: PasswordResetConfirm, db: Session = Depends(get_db)):
    """Reset password using the token sent via email"""
    try:
        user = reset_password(db, request.token, request.new_password)
        return {
            "message": "Password reset successfully",
            "email": user.email
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ===================== USER INFO =====================
# ✅ CORRECT WAY: Just use Depends(get_current_user) - Swagger will pick it up automatically

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user info",
    responses={
        401: {"description": "Not authenticated"},
        200: {"description": "Successful Response"}
    }
)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Returns the current authenticated user's info.
    Requires Bearer token.
    """
    return current_user


@router.get(
    "/me/profile",
    summary="Get user profile with role-specific data"
)
def get_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's full profile"""
    if current_user.role == UserRole.JOB_SEEKER:
        profile = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Job seeker profile not found")
        return {
            "user": current_user,
            "profile": profile,
            "role": "job_seeker"
        }
    
    elif current_user.role == UserRole.EMPLOYER:
        profile = db.query(Employer).filter(Employer.user_id == current_user.id).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Employer profile not found")
        return {
            "user": current_user,
            "profile": profile,
            "role": "employer"
        }
    
    else:
        return {
            "user": current_user,
            "role": "admin"
        }
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


router = APIRouter(prefix="/auth", tags=["authentication"])

# ===================== RATE LIMITING =====================
# Simple in-memory rate limiter (move to Redis in production)
from collections import defaultdict
from datetime import datetime

_rate_limit_store = defaultdict(list)

def check_rate_limit(email: str, max_attempts: int = 5, window_minutes: int = 60):
    """Prevent registration spam"""
    now = datetime.now()
    cutoff = now - timedelta(minutes=window_minutes)
    
    # Clean old attempts
    _rate_limit_store[email] = [
        attempt for attempt in _rate_limit_store[email]
        if attempt > cutoff
    ]
    
    # Check limit
    if len(_rate_limit_store[email]) >= max_attempts:
        raise HTTPException(
            status_code=429,
            detail=f"Too many registration attempts. Please try again in {window_minutes} minutes.",
            headers={"Retry-After": str(window_minutes * 60)}
        )
    
    # Record attempt
    _rate_limit_store[email].append(now)


# ===================== REGISTRATION =====================

# app/routes/auth_routes.py

@router.post("/register/job-seeker/basic", status_code=status.HTTP_201_CREATED)
def register_job_seeker(user: JobSeekerBasicRegistration, db: Session = Depends(get_db)):
    """
    Job Seeker Registration - Matches Employer Flow
    
    Flow:
    1. Register with email/password/name → Email verification sent
    2. User verifies email → Can now login
    3. User uploads CV (optional but recommended) → Profile auto-populated
    4. User can browse/apply to jobs
    
    CV upload is NOT required to activate account (unlike old flow)
    """
    
    # ✅ Rate limiting
    check_rate_limit(user.email)
    
    # Check if user already exists
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

    
    # ✅ Create user with is_active=True (matches employer pattern)
    new_user = User(
        email=user.email,
        hashed_password=hash_password(user.password),
        role=UserRole.JOB_SEEKER,
        is_active=True,  # ✅ CHANGED: User is active immediately (can login after email verification)
        is_email_verified=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # ✅ Create minimal job seeker profile
    job_seeker = JobSeeker(
        user_id=new_user.id,
        full_name=user.full_name,
        profile_completed=False  # Will become True after CV upload
    )
    db.add(job_seeker)
    db.commit()
    
    # ✅ Generate and SEND email verification immediately
    token = create_email_verification_token(db, new_user)
    send_verification_email(new_user.email, token)
    
    return {
        "message": "Registration successful! Please check your email to verify your account.",
        "user_id": str(new_user.id),
        "email": new_user.email,
        "next_step": "email_verification",
        "instructions": "Check your inbox and click the verification link. After verification, you can login and optionally upload your CV for better job matching."
    }


@router.post("/register/employer", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_employer(user: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new employer account
    """
    # Check if user already exists
    existing_user = user_crud.get_user_by_email(db, user.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user with EMPLOYER role
    new_user = user_crud.create_user(db, user.email, UserRole.EMPLOYER, user.password)  # ← FIXED
    
    # Create Employer profile
    employer = Employer(
        user_id=new_user.id,
        company_name=user.full_name,  # ✅ Use full_name as initial company name
        company_email=user.email,     # ← ADD THIS (required by Employer model)
        profile_completed=False,
        is_verified=False
    )
    db.add(employer)
    db.commit()
    db.refresh(employer)
    
    # Generate email verification token
    token = create_email_verification_token(db, new_user)
    
    # Send verification email
    send_verification_email(new_user.email, token)
    
    return new_user


# ===================== LOGIN =====================
@router.post("/login", response_model=Token)
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
    
    # ✅ REMOVED: is_active check (now always True)
    
    # Only check email verification
    if not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please check your inbox.",
            headers={
                "X-Next-Step": "email_verification",
                "X-User-Email": user.email
            }
        )
    
    # Create access token
    access_token = create_access_token(
        data={"sub": str(user.id)}, 
        expires_delta=timedelta(minutes=60 * 24)
    )
    
    # Add profile completion status for job seekers
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

@router.post("/verify-email/request")
def request_email_verification(
    request: EmailVerificationRequest,
    db: Session = Depends(get_db)
):
    """
    Request a new email verification token
    """
    user = user_crud.get_user_by_email(db, request.email)
    
    if not user:
        # Don't reveal if email exists or not (security best practice)
        return {"message": "If email exists, verification link has been sent"}
    
    if user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified"
        )
    
    # Generate new token
    token = create_email_verification_token(db, user)
    
    # Send verification email
    send_verification_email(user.email, token)  # ← ACTIVATED
    
    return {"message": "Verification email sent"}


@router.post("/verify-email/confirm")
def confirm_email_verification(
    request: EmailVerificationConfirm,
    db: Session = Depends(get_db)
):
    """
    Verify email using the token sent via email
    """
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

@router.post("/password-reset/request")
def request_password_reset(
    request: PasswordResetRequest,
    db: Session = Depends(get_db)
):
    """
    Request a password reset token
    """
    user = user_crud.get_user_by_email(db, request.email)
    
    if not user:
        # Don't reveal if email exists or not (security best practice)
        return {"message": "If email exists, password reset link has been sent"}
    
    try:
        token = create_password_reset_token(db, user)
        
        # Send password reset email
        send_password_reset_email(user.email, token)  # ← ACTIVATED
        
        return {"message": "Password reset link sent to email"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/password-reset/confirm")
def confirm_password_reset(
    request: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """
    Reset password using the token sent via email
    """
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

@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user's information
    """
    return current_user


@router.get("/me/profile")
def get_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's full profile (with job seeker or employer data)
    """
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

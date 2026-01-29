from sqlalchemy.orm import Session
from app.models.user import User
from app.models.password_reset import PasswordResetToken
from datetime import datetime, timedelta, timezone
import secrets
from app.models.employer import Employer
import uuid
import logging

logger = logging.getLogger(__name__)


# ===================== EMAIL VERIFICATION =====================

def create_email_verification_token(db: Session, user: User) -> str:
    """Generate email verification token (expires in 24 hours)"""
    
    # FORCE new token creation if user is being re-verified
    # Don't reuse old tokens - they cause issues with deleted/recreated users
    if user.email_verification_token and user.email_verification_expiry:
        if user.email_verification_expiry > datetime.now(timezone.utc):
            print(f"♻️ Reusing valid token for {user.email}")
            return user.email_verification_token
        else:
            print(f"🗑️ Old token expired, creating new one for {user.email}")
    
    # Generate fresh token
    token = secrets.token_urlsafe(32)
    user.email_verification_token = token
    user.email_verification_expiry = datetime.now(timezone.utc) + timedelta(hours=24)
    
    print("="*50)
    print("DEBUG: CREATING NEW TOKEN")
    print(f"User: {user.email}")
    print(f"Token: {token}")
    print(f"Expiry: {user.email_verification_expiry}")
    print("="*50)
    
    db.commit()
    db.refresh(user)
    return token

def verify_email(db: Session, token: str) -> User:
    """Verify email using token"""
    logger.info(f"===== EMAIL VERIFICATION DEBUG =====")
    logger.info(f"Received token: {token}")
    logger.info(f"Token length: {len(token)}")
    logger.info(f"Current time: {datetime.now(timezone.utc)}")
    
    # Check if ANY user has this token (ignore expiry first)
    user_with_token = db.query(User).filter(
        User.email_verification_token == token
    ).first()
    
    if user_with_token:
        logger.info(f"Found user with token: {user_with_token.email}")
        logger.info(f"Token expiry: {user_with_token.email_verification_expiry}")
        
        # Check if expiry is None
        if user_with_token.email_verification_expiry is None:
            logger.error(f"⚠️ TOKEN EXPIRY IS NONE! This means create_email_verification_token didn't save it properly")
        else:
            logger.info(f"Token expired: {user_with_token.email_verification_expiry < datetime.now(timezone.utc)}")
    else:
        logger.warning(f"NO USER FOUND WITH TOKEN: {token}")
        # List all tokens in database for debugging
        all_users = db.query(User).filter(User.email_verification_token.isnot(None)).all()
        logger.info(f"All users with tokens: {[(u.email, u.email_verification_token[:20] if u.email_verification_token else 'None') for u in all_users]}")
    
    # Original query with expiry check
    user = db.query(User).filter(
        User.email_verification_token == token,
        User.email_verification_expiry > datetime.now(timezone.utc)
    ).first()
    
    if not user:
        raise ValueError("Invalid or expired verification token")
    
    logger.info(f"✅ Verification successful for {user.email}")
    
    user.is_email_verified = True
    user.email_verification_token = None
    user.email_verification_expiry = None
    
    db.commit()
    db.refresh(user)
    return user




# ===================== WORK EMAIL VERIFICATION (EMPLOYERS) =====================

def create_work_email_verification_token(db: Session, employer: Employer) -> str:
    """
    Generate a 6-digit verification code for work email
    Similar to 2FA codes
    """
    # Generate 6-digit code
    code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])

    employer.work_email_verification_token = code
    employer.work_email_verification_sent_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(employer)

    return code


def verify_work_email(db: Session, employer_id: uuid.UUID, code: str) -> Employer:
    """
    Verify work email with 6-digit code
    Code expires after 15 minutes
    """
    employer = db.query(Employer).filter(Employer.id == employer_id).first()

    if not employer:
        raise ValueError("Employer not found")

    if employer.work_email_verified:
        raise ValueError("Work email already verified")

    if not employer.work_email_verification_token:
        raise ValueError("No verification code found. Please request a new code")

    # Check expiration (15 minutes)
    if employer.work_email_verification_sent_at:
        expiry_time = employer.work_email_verification_sent_at + timedelta(minutes=15)
        if datetime.now(timezone.utc) > expiry_time:
            raise ValueError("Verification code expired. Please request a new code")

    # Verify code
    if employer.work_email_verification_token != code:
        raise ValueError("Invalid verification code")

    # Mark as verified
    employer.work_email_verified = True
    employer.work_email_verified_at = datetime.now(timezone.utc)
    employer.work_email_verification_token = None  # Clear token

    # UPGRADE TO EMAIL_VERIFIED TIER (only if domain matches)
    if employer.verification_tier == "UNVERIFIED":
        # Verify domain match
        email_domain = employer.work_email.split('@')[-1]
        website_domain = None

        if employer.company_website:
            website_clean = employer.company_website.replace('https://', '').replace('http://', '').replace('www.', '')
            website_domain = website_clean.split('/')[0]

            # Extract base domains
            email_base = '.'.join(email_domain.split('.')[-2:])
            website_base = '.'.join(website_domain.split('.')[-2:])

            # Check for generic email domains
            generic_domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com']

            if email_domain in generic_domains:
                # Generic email - lower trust score
                employer.verification_tier = "EMAIL_VERIFIED"
                employer.trust_score = 40
            elif email_base == website_base:
                # Domain match - good trust score
                employer.verification_tier = "EMAIL_VERIFIED"
                employer.trust_score = 60
            else:
                # Domain mismatch but email verified
                employer.verification_tier = "EMAIL_VERIFIED"
                employer.trust_score = 45
        else:
            # No website but work email verified (for startups)
            employer.verification_tier = "EMAIL_VERIFIED"
            employer.trust_score = 40

    db.commit()
    db.refresh(employer)

    return employer


def resend_work_email_verification(db: Session, employer_id: uuid.UUID) -> str:
    """
    Resend work email verification code
    Implements rate limiting (1 request per 2 minutes)
    """
    employer = db.query(Employer).filter(Employer.id == employer_id).first()

    if not employer:
        raise ValueError("Employer not found")

    if employer.work_email_verified:
        raise ValueError("Work email already verified")

    # Rate limiting: Allow resend only after 2 minutes
    if employer.work_email_verification_sent_at:
        time_since_last = datetime.now(timezone.utc) - employer.work_email_verification_sent_at
        if time_since_last < timedelta(minutes=2):
            seconds_remaining = 120 - int(time_since_last.total_seconds())
            raise ValueError(f"Please wait {seconds_remaining} seconds before requesting a new code")

    # Generate new code
    code = create_work_email_verification_token(db, employer)

    return code


# ===================== PASSWORD RESET =====================

def create_password_reset_token(db: Session, user: User) -> str:
    """Generate password reset token (expires in 1 hour)"""
    # Check if user has a password (OAuth users don't)
    if not user.hashed_password:
        raise ValueError("OAuth users cannot reset password. Please login with your social account.")
    
    token = secrets.token_urlsafe(32)
    
    # Delete any existing tokens for this user
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).delete()
    
    reset_token = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1)  # ✅ Fixed timezone
    )
    db.add(reset_token)
    db.commit()
    return token


def reset_password(db: Session, token: str, new_password: str) -> User:
    """Reset user password using token"""
    from app.utils.security import hash_password
    
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token
    ).first()
    
    if not reset_token:
        raise ValueError("Invalid reset token")
    
    if datetime.now(timezone.utc) > reset_token.expires_at:  # ✅ Fixed timezone
        db.delete(reset_token)
        db.commit()
        raise ValueError("Reset token expired. Please request a new one.")
    
    user = db.query(User).filter(User.id == reset_token.user_id).first()
    if not user:
        raise ValueError("User not found")
    
    user.hashed_password = hash_password(new_password)
    db.delete(reset_token)
    db.commit()
    db.refresh(user)
    return user


# ===================== OAUTH =====================

def get_or_create_oauth_user(db: Session, email: str, provider: str, provider_id: str) -> User:
    """Get existing OAuth user or create new one"""
    from app.models.user import UserRole
    
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            role=UserRole.JOB_SEEKER,
            oauth_provider=provider,
            oauth_provider_id=provider_id,
            is_email_verified=True,  # OAuth emails are pre-verified
            is_active=True  # ✅ Active by default (matches new flow)
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

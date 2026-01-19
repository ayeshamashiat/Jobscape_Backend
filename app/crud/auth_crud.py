from sqlalchemy.orm import Session
from app.models.user import User
from app.models.password_reset import PasswordResetToken
from datetime import datetime, timedelta, timezone
import secrets

# ----------------- Email Verification -----------------
def create_email_verification_token(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    user.email_verification_token = token
    user.email_verification_expiry = datetime.utcnow() + timedelta(hours=24)
    db.commit()
    db.refresh(user)
    return token

def verify_email(db: Session, token: str) -> User:
    user = db.query(User).filter(
        User.email_verification_token == token,
        User.email_verification_expiry > datetime.utcnow()
    ).first()
    
    if not user:
        raise ValueError("Invalid or expired verification token")
    
    user.is_email_verified = True
    user.email_verification_token = None
    user.email_verification_expiry = None
    db.commit()
    db.refresh(user)
    return user

# ----------------- Password Reset -----------------
def create_password_reset_token(db: Session, user: User) -> str:
    # Check if user has a password (OAuth users don't)
    if not user.hashed_password:
        raise ValueError("OAuth users cannot reset password")
    
    token = secrets.token_urlsafe(32)
    
    # Delete any existing tokens for this user
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).delete()
    
    reset_token = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=datetime.utcnow() + timedelta(hours=1)
    )
    db.add(reset_token)
    db.commit()
    return token

def reset_password(db: Session, token: str, new_password: str) -> User:
    from app.utils.security import hash_password
    
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token
    ).first()
    
    if not reset_token:
        raise ValueError("Invalid token")
    
    if datetime.utcnow() > reset_token.expires_at:
        db.delete(reset_token)
        db.commit()
        raise ValueError("Token expired")
    
    user = db.query(User).filter(User.id == reset_token.user_id).first()
    if not user:
        raise ValueError("User not found")
    
    user.hashed_password = hash_password(new_password)
    db.delete(reset_token)
    db.commit()
    db.refresh(user)
    return user

# ----------------- OAuth -----------------
def get_or_create_oauth_user(db: Session, email: str, provider: str, provider_id: str) -> User:
    from app.models.user import UserRole
    
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            role=UserRole.JOB_SEEKER,
            oauth_provider=provider,
            oauth_provider_id=provider_id,
            is_email_verified=True  # OAuth emails are pre-verified
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

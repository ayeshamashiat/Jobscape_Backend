from sqlalchemy.orm import Session
from app.models.user import User, UserRole
from app.utils.security import hash_password
from datetime import datetime, timedelta
import secrets

# ----------------- Email Verification -----------------
def set_email_verified(db: Session, user: User):
    user.is_email_verified = True
    db.commit()
    db.refresh(user)
    return user

# ----------------- Password Reset -----------------
def create_password_reset_token(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    user.password_reset_token = token
    user.password_reset_expiry = datetime.utcnow() + timedelta(hours=1)
    db.commit()
    db.refresh(user)
    return token

def reset_password(db: Session, token: str, new_password: str) -> User:
    user = db.query(User).filter(User.password_reset_token == token).first()
    if not user:
        raise ValueError("Invalid token")
    if datetime.utcnow() > user.password_reset_expiry:
        raise ValueError("Token expired")
    user.hashed_password = hash_password(new_password)
    user.password_reset_token = None
    user.password_reset_expiry = None
    db.commit()
    db.refresh(user)
    return user

# ----------------- OAuth -----------------
def get_or_create_oauth_user(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        # default OAuth users are job seekers
        user = User(email=email, role=UserRole.JOB_SEEKER)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

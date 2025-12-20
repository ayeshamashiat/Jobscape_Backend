from sqlalchemy.orm import Session
from app.models.user import User, UserRole
from app.utils.security import hash_password, verify_password

def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, email: str, role: UserRole, password: str | None = None) -> User:
    hashed_pw = hash_password(password) if password else None
    user = User(email=email, role=role, hashed_password=hashed_pw)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def create_job_seeker(db: Session, email: str, password: str) -> User:
    if get_user_by_email(db, email):
        raise ValueError("Email already registered")
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    return create_user(db, email, UserRole.JOB_SEEKER, password)

def create_employer(db: Session, email: str, password: str) -> User:
    if get_user_by_email(db, email):
        raise ValueError("Email already registered")
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    return create_user(db, email, UserRole.EMPLOYER, password)

def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if user is None or user.hashed_password is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm

from app.database import get_db
from app.crud import user_crud
from app.schema.user_schema import UserCreate, UserResponse, Token
from app.models.user import UserRole
from app.utils.security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

#Email/password registration
@router.post("/register", response_model=UserResponse)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)):
    existing = user_crud.get_user_by_email(db, user_in.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    if not user_in.password:
        raise HTTPException(status_code=400, detail="Password required for email registration")

    user = user_crud.create_user(db, email=user_in.email, role=user_in.role, password=user_in.password)
    return user


# Email/password login
@router.post("/login", response_model=Token)
def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = user_crud.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return {"access_token": token, "token_type": "bearer"}

#OAuth 
@router.post("/oauth", response_model=Token)
def oauth_login(email: str, role: UserRole, db: Session = Depends(get_db)):
    user = user_crud.get_user_by_email(db, email)
    if not user:
        user = user_crud.create_user(db, email=email, role=role)
    
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return {"access_token": token, "token_type": "bearer"}

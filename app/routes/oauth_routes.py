from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schema.auth_schema import Token
from app.crud import auth_crud
from app.utils.security import create_access_token
from datetime import timedelta
from pydantic import BaseModel
import requests
import os

router = APIRouter(prefix="/oauth", tags=["oauth"])


class GoogleAuthRequest(BaseModel):
    id_token: str  # From Google Sign-In


class LinkedInAuthRequest(BaseModel):
    access_token: str  # From LinkedIn OAuth


@router.post("/google/login", response_model=Token)
def google_oauth_login(
    request: GoogleAuthRequest,
    db: Session = Depends(get_db)
):
    """Login/Register with Google OAuth"""
    try:
        # Verify token with Google
        response = requests.get(
            f"https://oauth2.googleapis.com/tokeninfo?id_token={request.id_token}"
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid Google token")
        
        user_info = response.json()
        email = user_info.get("email")
        provider_id = user_info.get("sub")
        full_name = user_info.get("name")  # ✅ GET NAME FROM GOOGLE
        
        if not email:
            raise HTTPException(status_code=400, detail="Email not found in Google account")
        
        # Check if user exists
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            # ✅ CREATE USER
            user = User(
                email=email,
                role=UserRole.JOB_SEEKER,
                oauth_provider="google",
                oauth_provider_id=provider_id,
                is_email_verified=True  # Google emails are pre-verified
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            
            # ✅ CREATE JOB SEEKER PROFILE WITH GOOGLE NAME
            job_seeker = JobSeeker(
                user_id=user.id,
                full_name=full_name or email.split('@')[0],  # Use Google name or email prefix
                profile_completed=False  # Not complete until CV uploaded
            )
            db.add(job_seeker)
            db.commit()
        
        # Create access token
        access_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=timedelta(hours=24)
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer"
        }
    
    except requests.exceptions.RequestException:
        raise HTTPException(status_code=401, detail="Failed to verify Google token")

@router.post("/linkedin/login", response_model=Token)
def linkedin_oauth_login(
    request: LinkedInAuthRequest,
    db: Session = Depends(get_db)
):
    """
    Login/Register with LinkedIn OAuth
    """
    try:
        # Get user info from LinkedIn
        response = requests.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={
                "Authorization": f"Bearer {request.access_token}"
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid LinkedIn token"
            )
        
        user_info = response.json()
        email = user_info.get("email")
        provider_id = user_info.get("sub")
        
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not found in LinkedIn account"
            )
        
        # Get or create user
        user = auth_crud.get_or_create_oauth_user(
            db=db,
            email=email,
            provider="linkedin",
            provider_id=provider_id
        )
        
        # Create access token
        access_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=timedelta(hours=24)
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer"
        }
    
    except requests.exceptions.RequestException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to verify LinkedIn token"
        )


@router.post("/github/login", response_model=Token)
def github_oauth_login(
    request: LinkedInAuthRequest,  # Same structure: access_token
    db: Session = Depends(get_db)
):
    """
    Login/Register with GitHub OAuth
    """
    try:
        # Get user info from GitHub
        response = requests.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {request.access_token}",
                "Accept": "application/vnd.github+json"
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid GitHub token"
            )
        
        user_info = response.json()
        
        # Get primary email
        email_response = requests.get(
            "https://api.github.com/user/emails",
            headers={
                "Authorization": f"Bearer {request.access_token}",
                "Accept": "application/vnd.github+json"
            }
        )
        
        if email_response.status_code == 200:
            emails = email_response.json()
            primary_email = next((e for e in emails if e.get("primary")), None)
            email = primary_email.get("email") if primary_email else user_info.get("email")
        else:
            email = user_info.get("email")
        
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not found in GitHub account"
            )
        
        provider_id = str(user_info.get("id"))
        
        # Get or create user
        user = auth_crud.get_or_create_oauth_user(
            db=db,
            email=email,
            provider="github",
            provider_id=provider_id
        )
        
        # Create access token
        access_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=timedelta(hours=24)
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer"
        }
    
    except requests.exceptions.RequestException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to verify GitHub token"
        )

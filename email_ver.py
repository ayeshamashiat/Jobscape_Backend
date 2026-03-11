# In Python shell or a test script
from app.database import SessionLocal
from app.models.user import User
from app.models.job_seeker import JobSeeker
from app.models.resume import Resume
from app.models.employer import Employer
from app.models.application import Application
from app.crud.auth_crud import create_email_verification_token, verify_email
from app.crud.user_crud import get_user_by_email

db = SessionLocal()

# Get a test user
user = get_user_by_email(db, "ayeshamashiat007@gmail.com")

# Create token
token = create_email_verification_token(db, user)
print(f"Generated token: {token}")

# Immediately verify it
verified_user = verify_email(db, token)
print(f"Verified: {verified_user.email}")

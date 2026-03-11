from app.database import SessionLocal
from app.models.user import User
from app.utils.security import verify_password

def test_login():
    db = SessionLocal()
    email = "verified@techcorp.com"
    user = db.query(User).filter(User.email == email).first()
    
    print("\n--- TEST LOGIN ---")
    if not user:
        print(f"User {email} NOT FOUND in DB!")
        return

    print(f"User found: {user.email}")
    print(f"Is Active: {user.is_active}")
    print(f"Is Email Verified: {user.is_email_verified}")
    
    password = "employer123"
    is_valid = verify_password(password, user.hashed_password)
    
    print(f"Password '{password}' valid? -> {is_valid}")
    if not is_valid:
        print(f"Expected Hash: {user.hashed_password[:20]}...")
    
    print("------------------\n")

if __name__ == "__main__":
    test_login()

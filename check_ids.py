from app.database import SessionLocal
from app.models.job import Job
from app.models.employer import Employer
from app.models.user import User

def check_ids():
    db = SessionLocal()
    print("\n--- DATABASE DIAGNOSTIC ---")
    
    # Get any job
    job = db.query(Job).first()
    if not job:
        print("No jobs found in DB!")
        return

    print(f"Job ID: {job.id}")
    print(f"Job Title: {job.title}")
    print(f"Job Employer ID (FK): {job.employer_id}")
    
    # Check if employer_id exists in employers table
    employer = db.query(Employer).filter(Employer.id == job.employer_id).first()
    if employer:
        print(f"Employer match FOUND! Employer ID: {employer.id}")
        print(f"Employer Company Name: {employer.company_name}")
        print(f"Employer User ID: {employer.user_id}")
    else:
        print(f"Employer match NOT FOUND for ID {job.employer_id}")
        
        # See if it matches a User ID
        user = db.query(User).filter(User.id == job.employer_id).first()
        if user:
            print(f"BUT ID matches a USER record! User Email: {user.email}")
            # Try to find the employer record for this user
            emp_by_user = db.query(Employer).filter(Employer.user_id == user.id).first()
            if emp_by_user:
                print(f"Found Employer record for this user! Employer ID: {emp_by_user.id}")
        else:
            print("ID does not match any USER record either.")

    print("---------------------------\n")
    db.close()

if __name__ == "__main__":
    check_ids()

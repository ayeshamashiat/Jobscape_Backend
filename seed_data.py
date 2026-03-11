# app/seed_data.py
"""
Enhanced database seeder for testing ATS matching and diverse jobs.
Run: python -m app.seed_data
"""

from app.database import SessionLocal, engine
from app.utils.security import hash_password
from datetime import datetime, timezone, timedelta
import uuid

# ===== IMPORT ALL MODELS FIRST =====
from app.models.user import User, UserRole, Base
from app.models.employer import Employer
from app.models.job_seeker import JobSeeker
from app.models.job import Job, JobType, WorkMode, ExperienceLevel
from app.models.password_reset import PasswordResetToken 

try:
    from app.models.resume import Resume
except ImportError:
    Resume = None

try:
    from app.models.application import Application, ApplicationStatus
except ImportError:
    Application = None

try:
    from app.models.selection_round import SelectionProcess
except ImportError:
    pass

import random

# Create tables AFTER all imports
Base.metadata.create_all(bind=engine)

def seed_database():
    db = SessionLocal()
    
    try:
        # Clear existing data (in correct order to avoid FK constraints)
        print("🗑️  Clearing existing data...")
        
        # Delete in reverse dependency order
        if Application:
            db.query(Application).delete()
        if Resume:
            db.query(Resume).delete()
        db.query(Job).delete()
        db.query(JobSeeker).delete()
        db.query(Employer).delete()
        db.query(User).delete()
        db.commit()
        
        # ===== CREATE ADMIN =====
        print("👑 Creating admin account...")
        admin_user = User(
            email="ayeshamashiat01@gmail.com",
            hashed_password=hash_password("admin123"),
            role=UserRole.ADMIN,
            is_active=True,
            is_email_verified=True
        )
        db.add(admin_user)
        db.commit()
        
        # ===== CREATE TEST EMPLOYERS =====
        print("\n🏢 Creating test employers...")
        
        employers_data = [
            {
                "email": "verified@techcorp.com",
                "password": "employer123",
                "company_name": "TechCorp Ltd",
                "company_website": "https://techcorp.com",
                "industry": "Software Development",
                "location": "Dhaka, Bangladesh",
                "tier": "FULLY_VERIFIED",
                "full_name": "Sarah Ahmed",
                "job_title": "HR Manager",
                "work_email": "sarah@techcorp.com",
                "trust_score": 95
            },
            {
                "email": "startup@innovate.io",
                "password": "employer123",
                "company_name": "Innovate Startup",
                "company_website": "https://innovate.io",
                "industry": "Fintech",
                "location": "Chittagong, Bangladesh",
                "tier": "EMAIL_VERIFIED",
                "full_name": "Rafiq Hassan",
                "job_title": "Founder",
                "work_email": "rafiq@innovate.io",
                "trust_score": 60
            }
        ]
        
        created_employers = []
        for emp_data in employers_data:
            user = User(
                email=emp_data["email"],
                hashed_password=hash_password(emp_data["password"]),
                role=UserRole.EMPLOYER,
                is_active=True,
                is_email_verified=True
            )
            db.add(user)
            db.flush()
            
            employer = Employer(
                user_id=user.id,
                full_name=emp_data["full_name"],
                job_title=emp_data["job_title"],
                work_email=emp_data["work_email"],
                work_email_verified=(emp_data["tier"] != "UNVERIFIED"),
                company_name=emp_data["company_name"],
                company_email=emp_data["email"],
                company_website=emp_data["company_website"],
                industry=emp_data["industry"],
                location=emp_data["location"],
                company_size="51-200",
                description=f"Leading {emp_data['industry']} company.",
                verification_tier=emp_data["tier"],
                trust_score=emp_data["trust_score"],
                profile_completed=True,
                verified_at=datetime.now(timezone.utc) if emp_data["tier"] == "FULLY_VERIFIED" else None
            )
            db.add(employer)
            db.flush()
            created_employers.append((emp_data["email"], emp_data["company_name"], employer))
        
        db.commit()
        
        # ===== CREATE DIVERSE JOBS =====
        print("\n💼 Creating diverse test jobs...")
        
        verified_employer = created_employers[0][2]  # TechCorp
        
        jobs_data = [
            {
                "title": "Senior Data Scientist",
                "description": "We are seeking a seasoned Data Scientist to lead our AI initiatives. Must be proficient in Python, PyTorch, and classical machine learning algorithms. You will build predictive models and analyze large datasets.",
                "salary_min": 100000,
                "salary_max": 180000,
                "location": "Dhaka",
                "work_mode": WorkMode.HYBRID,
                "job_type": JobType.FULL_TIME,
                "experience_level": ExperienceLevel.SENIOR,
                "required_skills": ["Python", "Machine Learning", "PyTorch", "SQL", "Pandas"],
                "preferred_skills": ["AWS", "Docker", "NLP"],
                "is_fresh_graduate_friendly": False,
                "hiring_policy": "Strict ATS threshold required.",
                "ats_threshold": 70
            },
            {
                "title": "Junior Frontend Developer",
                "description": "Looking for a talented frontend developer to join our team. Fresh graduates welcome! Must know React.",
                "salary_min": 40000,
                "salary_max": 60000,
                "location": "Dhaka",
                "work_mode": WorkMode.REMOTE,
                "job_type": JobType.FULL_TIME,
                "experience_level": ExperienceLevel.ENTRY,
                "required_skills": ["React", "JavaScript", "HTML", "CSS"],
                "preferred_skills": ["TypeScript", "Tailwind CSS"],
                "is_fresh_graduate_friendly": True,
                "ats_threshold": 40
            },
            {
                "title": "Product Manager",
                "description": "Lead cross-functional teams to deliver impactful software products.",
                "salary_min": 90000,
                "salary_max": 150000,
                "location": "Chittagong",
                "work_mode": WorkMode.ONSITE,
                "job_type": JobType.FULL_TIME,
                "experience_level": ExperienceLevel.MID,
                "required_skills": ["Product Management", "Agile", "Scrum", "Jira"],
                "preferred_skills": ["UX Principles", "Data Analytics"],
                "is_fresh_graduate_friendly": False,
                "ats_threshold": 60
            },
            {
                "title": "DevOps Engineer",
                "description": "Manage our cloud infrastructure and CI/CD pipelines.",
                "salary_min": 90000,
                "salary_max": 140000,
                "location": "Dhaka",
                "work_mode": WorkMode.REMOTE,
                "job_type": JobType.FULL_TIME,
                "experience_level": ExperienceLevel.MID,
                "required_skills": ["AWS", "Docker", "Kubernetes", "Linux", "CI/CD"],
                "preferred_skills": ["Terraform", "Jenkins", "Python"],
                "is_fresh_graduate_friendly": False,
                "ats_threshold": 65
            }
        ]
        
        created_jobs = []
        for job_data in jobs_data:
            job = Job(
                employer_id=verified_employer.id,
                title=job_data["title"],
                description=job_data["description"],
                salary_min=job_data["salary_min"],
                salary_max=job_data["salary_max"],
                location=job_data["location"],
                work_mode=job_data["work_mode"],
                job_type=job_data["job_type"],
                experience_level=job_data["experience_level"],
                required_skills=job_data["required_skills"],
                preferred_skills=job_data["preferred_skills"],
                is_fresh_graduate_friendly=job_data["is_fresh_graduate_friendly"],
                hiring_policy=job_data.get("hiring_policy"),
                ats_threshold=job_data.get("ats_threshold", 50),
                is_active=True,
                is_closed=False,
                application_deadline=datetime.now(timezone.utc) + timedelta(days=30)
            )
            db.add(job)
            db.flush()
            created_jobs.append(job)
        
        target_job = created_jobs[0] # Senior Data Scientist is our highly applied-to job
        db.commit()


        # ===== CREATE MASSIVE NUMBER OF JOB SEEKERS FOR ATS TESTING =====
        print(f"\n👤 Creating 25 diverse candidate applications for '{target_job.title}'...")
        
        # Skill templates to simulate various match scores
        perfect_match_skills = ["Python", "Machine Learning", "PyTorch", "SQL", "Pandas", "AWS", "Docker", "NLP"]
        good_match_skills = ["Python", "Machine Learning", "Scikit-Learn", "SQL", "TensorFlow"]
        mediocre_match_skills = ["Python", "Django", "SQL", "Git", "HTML"]
        bad_match_skills = ["Java", "Spring Boot", "Oracle Database", "Maven"]
        frontend_skills = ["React", "JavaScript", "HTML", "CSS", "Figma", "Redux"]
        
        applicant_profiles = []
        
        # Generate 25 seekers
        for i in range(1, 26):
            # Assign random skills to simulate varied ATS scores
            if i <= 5:
                skills = perfect_match_skills
                summary = "Senior Data Scientist with 5 years experience in building NLP and PyTorch models deployed via Docker on AWS. Strong Python and SQL skills."
                exp_level = 5
            elif i <= 10:
                skills = good_match_skills
                summary = "Data Scientist currently focusing on classical Machine Learning using Python, Pandas, and Scikit-Learn. Exploring deep learning."
                exp_level = 3
            elif i <= 15:
                skills = frontend_skills
                summary = "Frontend Developer passionate about UI UX. Expert in React and Javascript."
                exp_level = 2
            elif i <= 20:
                skills = bad_match_skills
                summary = "Enterprise Java developer focusing on Oracle and Spring Boot."
                exp_level = 4
            else:
                skills = mediocre_match_skills
                summary = "Backend Python Django developer looking to transition into data science. Knows SQL."
                exp_level = 1

            email = f"candidate{i}@test.com"
            user = User(
                email=email,
                hashed_password=hash_password("jobseeker123"),
                role=UserRole.JOB_SEEKER,
                is_active=True,
                is_email_verified=True
            )
            db.add(user)
            db.flush()
            
            job_seeker = JobSeeker(
                user_id=user.id,
                full_name=f"Candidate {i}",
                phone=f"+880 1712-0000{i:02d}",
                location="Dhaka, Bangladesh",
                professional_summary=summary,
                skills=skills,
                primary_industry="Technology",
                profile_completed=True
            )
            db.add(job_seeker)
            db.flush()
            
            # Create a mock parsed Resume
            if Resume:
                resume = Resume(
                    job_seeker_id=job_seeker.id,
                    file_url="https://res.cloudinary.com/demo/image/upload/sample.pdf",
                    is_primary=True,
                    parsed_data={
                        "skills": skills,
                        "experience": [{"title": "Software Engineer", "duration": f"{exp_level} years"}],
                        "summary": summary
                    }
                )
                db.add(resume)
                db.flush()
                
                # Simulate scores based on group
                if i <= 5:
                    match_score = random.randint(85, 98)
                elif i <= 10:
                    match_score = random.randint(65, 84)
                elif i <= 15:
                    match_score = random.randint(40, 64)
                elif i <= 20:
                    match_score = random.randint(20, 39)
                else:
                    match_score = random.randint(5, 19)

                # Apply to the Target Job
                if Application:
                    app = Application(
                        job_id=target_job.id,
                        job_seeker_id=job_seeker.id,
                        resume_id=resume.id,
                        cover_letter=f"Hi, I am very interested in this role. Here is my resume.",
                        status=ApplicationStatus.PENDING,
                        match_score=match_score,
                        skills_match={
                            "matched_required": skills[:2], 
                            "matched_preferred": skills[2:4] if len(skills)>2 else [], 
                            "missing_required": ["Missing Skill"]
                        },
                        current_round=0,
                        ats_score=match_score, # For simplicity, setting ats_score to mirror match_score
                        ats_report={"summary": "Mock ATS report", "score": match_score}
                    )
                    db.add(app)
        
        db.commit()
        
        print("\n" + "="*70)
        print("✅ DATABASE SEEDED SUCCESSFULLY WITH ATS TEST DATA!")
        print("="*70)
        print("\n📋 HIGHLIGHTS:")
        print(f"   - Created Job: '{target_job.title}'")
        print(f"   - Attached **25 candidates** with varied skillsets (Perfect matches, Frontend Devs, Java devs, etc).")
        print("   - You can now test Bulk ATS Scoring on this job as 'verified@techcorp.com'.")
        print("\n👑 ADMIN: ayeshamashiat01@gmail.com / admin123")
        print("🏢 EMPLOYER: verified@techcorp.com / employer123")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()

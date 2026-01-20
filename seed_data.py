# app/seed_data.py
"""
Seed database with test data
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

# Try importing Resume (if it exists)
try:
    from app.models.resume import Resume
except ImportError:
    Resume = None
    print("⚠️  Resume model not found, skipping...")

# Try importing other models that might exist
try:
    from app.models.application import Application
except ImportError:
    pass

try:
    from app.models.subscription import Subscription
except ImportError:
    pass

# Create tables AFTER all imports
Base.metadata.create_all(bind=engine)

def seed_database():
    db = SessionLocal()
    
    try:
        # Clear existing data (in correct order to avoid FK constraints)
        print("🗑️  Clearing existing data...")
        
        # Delete in reverse dependency order
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
        print(f"✅ Admin created: admin@jobscape.com / admin123")
        
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
            },
            {
                "email": "pending@bigcorp.com",
                "password": "employer123",
                "company_name": "Big Corp Industries",
                "company_website": "https://bigcorp.com",
                "industry": "Manufacturing",
                "location": "Sylhet, Bangladesh",
                "tier": "DOCUMENT_VERIFIED",
                "full_name": "Ayesha Khan",
                "job_title": "Recruitment Lead",
                "work_email": "ayesha@bigcorp.com",
                "trust_score": 75
            },
            {
                "email": "unverified@newcompany.com",
                "password": "employer123",
                "company_name": "New Company",
                "company_website": None,
                "industry": "E-commerce",
                "location": "Dhaka, Bangladesh",
                "tier": "UNVERIFIED",
                "full_name": "Mehedi Hasan",
                "job_title": "CEO",
                "work_email": "mehedi@newcompany.com",
                "trust_score": 20
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
                description=f"Leading {emp_data['industry']} company in Bangladesh",
                verification_tier=emp_data["tier"],
                trust_score=emp_data["trust_score"],
                profile_completed=True,
                verified_at=datetime.now(timezone.utc) if emp_data["tier"] == "FULLY_VERIFIED" else None
            )
            db.add(employer)
            db.flush()
            created_employers.append((emp_data["email"], emp_data["company_name"], employer))
            print(f"✅ Employer: {emp_data['email']} / employer123 [{emp_data['tier']}]")
        
        db.commit()
        
        # ===== CREATE TEST JOB SEEKERS =====
        print("\n👤 Creating test job seekers...")
        
        job_seekers_data = [
            {
                "email": "john.dev@gmail.com",
                "password": "jobseeker123",
                "full_name": "John Developer",
                "phone": "+880 1712-345678",
                "location": "Dhaka, Bangladesh",
                "professional_summary": "Experienced backend developer with 3+ years in Python and FastAPI. Passionate about building scalable systems.",
                "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS", "REST APIs"],
                "primary_industry": "Software Development",
                "inferred_industries": ["Software Development", "Technology", "Cloud Computing"],
                "experience": [
                    {
                        "title": "Backend Developer",
                        "company": "Tech Solutions Ltd",
                        "duration": "2021 - Present",
                        "description": "Built RESTful APIs using FastAPI and PostgreSQL"
                    }
                ],
                "education": [
                    {
                        "degree": "B.Sc. in Computer Science",
                        "institution": "University of Dhaka",
                        "year": "2020"
                    }
                ],
                "projects": [
                    {
                        "name": "E-commerce Backend",
                        "description": "Scalable microservices architecture",
                        "tech": ["Python", "Docker", "Redis"]
                    }
                ],
                "linkedin_url": "https://linkedin.com/in/johndev",
                "github_url": "https://github.com/johndev"
            },
            {
                "email": "sarah.designer@gmail.com",
                "password": "jobseeker123",
                "full_name": "Sarah Designer",
                "phone": "+880 1812-987654",
                "location": "Chittagong, Bangladesh",
                "professional_summary": "Creative UI/UX designer with a keen eye for detail and user-centered design.",
                "skills": ["UI/UX Design", "Figma", "Adobe XD", "Prototyping", "User Research"],
                "primary_industry": "Design",
                "inferred_industries": ["Design", "User Experience", "Digital Media"],
                "experience": [
                    {
                        "title": "UI/UX Designer",
                        "company": "Design Studio",
                        "duration": "2022 - Present",
                        "description": "Led design for mobile and web applications"
                    }
                ],
                "education": [
                    {
                        "degree": "B.A. in Graphic Design",
                        "institution": "Chittagong University",
                        "year": "2021"
                    }
                ],
                "portfolio_url": "https://sarahdesign.portfolio.com",
                "linkedin_url": "https://linkedin.com/in/sarahdesigner"
            },
            {
                "email": "fresh.grad@gmail.com",
                "password": "jobseeker123",
                "full_name": "Fresh Graduate",
                "phone": "+880 1912-456789",
                "location": "Dhaka, Bangladesh",
                "professional_summary": "Recent computer science graduate eager to start career in web development.",
                "skills": ["JavaScript", "React", "Node.js", "HTML", "CSS", "Git"],
                "primary_industry": "Software Development",
                "inferred_industries": ["Software Development", "Web Development"],
                "experience": [],
                "education": [
                    {
                        "degree": "B.Sc. in Computer Science",
                        "institution": "BRAC University",
                        "year": "2025"
                    }
                ],
                "projects": [
                    {
                        "name": "Personal Blog",
                        "description": "Built with React and Node.js",
                        "tech": ["React", "Node.js", "MongoDB"]
                    }
                ],
                "github_url": "https://github.com/freshgrad"
            }
        ]
        
        for js_data in job_seekers_data:
            user = User(
                email=js_data["email"],
                hashed_password=hash_password(js_data["password"]),
                role=UserRole.JOB_SEEKER,
                is_active=True,  # Make active for testing (skip CV requirement)
                is_email_verified=True
            )
            db.add(user)
            db.flush()
            
            # Create JobSeeker with all available fields
            job_seeker = JobSeeker(
                user_id=user.id,
                full_name=js_data["full_name"],
                phone=js_data.get("phone"),
                location=js_data.get("location"),
                professional_summary=js_data.get("professional_summary"),
                skills=js_data.get("skills", []),
                primary_industry=js_data.get("primary_industry"),
                inferred_industries=js_data.get("inferred_industries", []),
                experience=js_data.get("experience", []),
                education=js_data.get("education", []),
                projects=js_data.get("projects", []),
                certifications=[],
                awards=[],
                languages=[],
                publications=[],
                volunteer_experience=[],
                linkedin_url=js_data.get("linkedin_url"),
                github_url=js_data.get("github_url"),
                portfolio_url=js_data.get("portfolio_url"),
                other_links=[],
                profile_completed=True
            )
            db.add(job_seeker)
            print(f"✅ Job Seeker: {js_data['email']} / jobseeker123")
        
        db.commit()
        
        # ===== CREATE TEST JOBS =====
        print("\n💼 Creating test jobs...")
        
        jobs_data = [
            {
                "title": "Senior Backend Developer",
                "description": "We need an experienced backend developer skilled in Python, FastAPI, and PostgreSQL. You'll be working on scalable microservices architecture.",
                "salary_min": 80000,
                "salary_max": 120000,
                "location": "Dhaka",
                "work_mode": WorkMode.HYBRID,
                "job_type": JobType.FULL_TIME,
                "experience_level": ExperienceLevel.SENIOR,
                "required_skills": ["Python", "FastAPI", "PostgreSQL"],
                "preferred_skills": ["Docker", "AWS"],
                "is_fresh_graduate_friendly": False
            },
            {
                "title": "Junior Frontend Developer",
                "description": "Looking for a talented frontend developer to join our team. Fresh graduates welcome!",
                "salary_min": 40000,
                "salary_max": 60000,
                "location": "Dhaka",
                "work_mode": WorkMode.REMOTE,
                "job_type": JobType.FULL_TIME,
                "experience_level": ExperienceLevel.ENTRY,
                "required_skills": ["React", "JavaScript", "CSS"],
                "preferred_skills": ["TypeScript", "Tailwind"],
                "is_fresh_graduate_friendly": True
            },
            {
                "title": "UI/UX Designer",
                "description": "Creative designer needed for product design and user research.",
                "salary_min": 50000,
                "salary_max": 80000,
                "location": "Chittagong",
                "work_mode": WorkMode.ONSITE,
                "job_type": JobType.FULL_TIME,
                "experience_level": ExperienceLevel.MID,
                "required_skills": ["Figma", "Adobe XD", "UI Design"],
                "preferred_skills": ["Prototyping", "User Research"],
                "is_fresh_graduate_friendly": False
            },
            {
                "title": "DevOps Engineer",
                "description": "Manage our cloud infrastructure and CI/CD pipelines.",
                "salary_min": 90000,
                "salary_max": 140000,
                "location": "Dhaka",
                "work_mode": WorkMode.HYBRID,
                "job_type": JobType.FULL_TIME,
                "experience_level": ExperienceLevel.SENIOR,
                "required_skills": ["AWS", "Docker", "Kubernetes"],
                "preferred_skills": ["Terraform", "Jenkins"],
                "is_fresh_graduate_friendly": False
            },
            {
                "title": "Marketing Intern",
                "description": "3-month internship for digital marketing enthusiasts.",
                "salary_min": 15000,
                "salary_max": 20000,
                "location": "Dhaka",
                "work_mode": WorkMode.ONSITE,
                "job_type": JobType.INTERNSHIP,
                "experience_level": ExperienceLevel.ENTRY,
                "required_skills": ["Social Media", "Content Writing"],
                "preferred_skills": ["SEO", "Analytics"],
                "is_fresh_graduate_friendly": True
            }
        ]
        
        # Only verified employer can post jobs
        verified_employer = created_employers[0][2]  # TechCorp
        
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
                is_active=True,
                is_closed=False,
                application_deadline=datetime.now(timezone.utc) + timedelta(days=30)
            )
            db.add(job)
            print(f"✅ Job: {job_data['title']}")
        
        db.commit()
        
        print("\n" + "="*70)
        print("✅ DATABASE SEEDED SUCCESSFULLY!")
        print("="*70)
        print("\n📋 TEST ACCOUNTS CREATED:")
        print("-"*70)
        print("\n👑 ADMIN:")
        print("   Email: admin@jobscape.com")
        print("   Password: admin123")
        print("\n🏢 EMPLOYERS (all use password: employer123):")
        for email, company, emp in created_employers:
            print(f"   - {email:30} | {company:25} | {emp.verification_tier}")
        print("\n👤 JOB SEEKERS (all use password: jobseeker123):")
        for js in job_seekers_data:
            print(f"   - {js['email']:30} | {js['full_name']}")
        print("\n💼 JOBS CREATED: 5 test jobs posted by TechCorp Ltd")
        print("-"*70)
        print("\n🚀 You can now start the backend and test:")
        print("   uvicorn app.main:app --reload")
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

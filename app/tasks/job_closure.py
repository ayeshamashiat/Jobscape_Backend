from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.job import Job
from app.models.employer import Employer
from datetime import datetime, timezone


def close_expired_jobs():
    """
    Auto-close jobs past their application deadline
    Run every hour or daily
    """
    db: Session = SessionLocal()
    
    try:
        now = datetime.now(timezone.utc)
        
        # Find jobs past deadline that are still active
        expired_jobs = db.query(Job).filter(
            Job.is_active == True,
            Job.is_closed == False,
            Job.application_deadline <= now
        ).all()
        
        closed_count = 0
        
        for job in expired_jobs:
            # Close the job
            job.is_active = False
            job.is_closed = True
            job.closed_at = now
            job.closure_reason = "deadline_passed"
            
            # Decrement employer's active counter
            employer = db.query(Employer).filter(Employer.id == job.employer_id).first()
            if employer and employer.active_job_posts_count > 0:
                employer.active_job_posts_count -= 1
            
            closed_count += 1
        
        db.commit()
        
        print(f"✅ Auto-closed {closed_count} jobs past deadline")
        return closed_count
    
    except Exception as e:
        db.rollback()
        print(f"❌ Error closing jobs: {e}")
        return 0
    finally:
        db.close()

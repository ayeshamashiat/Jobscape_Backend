from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone
import uuid

from app.database import get_db
from app.models.employer import Employer
from app.models.user import User, UserRole
from app.utils.security import get_current_user
from app.schema.employer_schema import EmployerProfileResponse, VerificationApprovalRequest

router = APIRouter(prefix="/admin", tags=["admin"])


# ===== ADMIN AUTHENTICATION =====

def require_admin(current_user: User = Depends(get_current_user)):
    """Dependency to ensure user is admin"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    return current_user


# ===== VERIFICATION QUEUE =====

@router.get("/verifications/pending")
def get_pending_verifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get all pending verification requests"""
    employers = db.query(Employer).filter(
        Employer.verification_tier == "DOCUMENT_VERIFIED"
    ).order_by(Employer.updated_at.desc()).offset(skip).limit(limit).all()
    
    total = db.query(Employer).filter(
        Employer.verification_tier == "DOCUMENT_VERIFIED"
    ).count()
    
    return {
        "items": employers,
        "total": total,
        "page": (skip // limit) + 1 if limit > 0 else 1,
        "has_more": (skip + limit) < total
    }


@router.get("/verifications/all")
def get_all_verifications(
    tier: Optional[str] = Query(None, regex="^(UNVERIFIED|EMAIL_VERIFIED|DOCUMENT_VERIFIED|FULLY_VERIFIED|REJECTED|SUSPENDED)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get all employers with optional tier filter"""
    query = db.query(Employer)
    
    if tier:
        query = query.filter(Employer.verification_tier == tier)
    
    total = query.count()
    employers = query.order_by(Employer.created_at.desc()).offset(skip).limit(limit).all()
    
    return {
        "items": employers,
        "total": total,
        "page": (skip // limit) + 1 if limit > 0 else 1,
        "pages": (total + limit - 1) // limit if limit > 0 else 1
    }


# ===== VERIFICATION DETAILS =====

@router.get("/verifications/{employer_id}")
def get_verification_details(
    employer_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get detailed verification info for specific employer"""
    employer = db.query(Employer).filter(Employer.id == employer_id).first()
    if not employer:
        raise HTTPException(status_code=404, detail="Employer not found")
    
    # Extract domains
    email_domain = employer.work_email.split("@")[-1] if employer.work_email else None
    website_domain = None
    if employer.company_website:
        website_clean = employer.company_website.replace("https://", "").replace("http://", "").replace("www.", "")
        website_domain = website_clean.split("/")[0]
    
    # Build verification checklist
    checklist = {
        "company_name": {
            "value": employer.company_name,
            "status": "pending",
            "instruction": "Search on RJSC website: https://app.roc.gov.bd/psp/nc_search"
        },
        "rjsc_number": {
            "value": employer.rjsc_registration_number or "Not provided",
            "status": "pending" if employer.rjsc_registration_number else "missing",
            "instruction": "Verify this number exists on RJSC database"
        },
        "work_email_domain": {
            "value": email_domain,
            "status": "pending",
            "instruction": f"Must match company website domain: {website_domain}"
        },
        "website": {
            "value": employer.company_website or "Not provided",
            "status": "pending" if employer.company_website else "missing",
            "instruction": "Visit website and verify it's legitimate"
        },
        "linkedin": {
            "value": "Check verification_notes field",
            "status": "pending",
            "instruction": "Search company on LinkedIn"
        },
        "google_search": {
            "value": f'Google: "{employer.company_name} Bangladesh"',
            "status": "pending",
            "instruction": "Check online presence"
        },
        "documents": {
            "value": f"{len(employer.verification_documents)} documents uploaded",
            "status": "pending",
            "instruction": "Check document authenticity"
        }
    }
    
    # Auto-check email domain match
    if email_domain and website_domain:
        email_base = '.'.join(email_domain.split('.')[-2:])
        website_base = '.'.join(website_domain.split('.')[-2:])
        
        if email_base == website_base:
            checklist["work_email_domain"]["status"] = "✅ PASS"
        else:
            checklist["work_email_domain"]["status"] = "❌ FAIL - SUSPICIOUS"
    
    # Count checks passed
    passed = sum(1 for check in checklist.values() if check["status"] == "✅ PASS")
    
    return {
        "employer": employer,
        "checklist": checklist,
        "checks_passed": passed,
        "checks_total": len(checklist),
        "recommendation": "Approve if at least 4 checks pass" if passed >= 4 else "More verification needed",
        "risk_level": "LOW" if passed >= 5 else "MEDIUM" if passed >= 3 else "HIGH"
    }


# ===== APPROVE VERIFICATION =====

@router.post("/verifications/{employer_id}/approve")
def approve_verification(
    employer_id: uuid.UUID,
    request: VerificationApprovalRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Approve employer verification"""
    employer = db.query(Employer).filter(Employer.id == employer_id).first()
    if not employer:
        raise HTTPException(status_code=404, detail="Employer not found")
    
    if employer.verification_tier not in ["DOCUMENT_VERIFIED", "REJECTED"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve employer with tier: {employer.verification_tier}"
        )
    
    # Update employer
    employer.verification_tier = "FULLY_VERIFIED"
    employer.verified_at = datetime.now(timezone.utc)
    employer.verified_by = admin.id
    employer.trust_score = 85
    
    # Append admin notes
    admin_note = f"\n\n✅ APPROVED by {admin.email}\nDate: {datetime.now(timezone.utc).isoformat()}\nReason: {request.admin_notes}"
    employer.verification_notes = (employer.verification_notes or "") + admin_note
    
    db.commit()
    db.refresh(employer)
    
    # TODO: Send congratulations email
    
    return {
        "message": "Employer verified successfully",
        "employer_id": str(employer.id),
        "company_name": employer.company_name,
        "verified_at": employer.verified_at
    }


# ===== REJECT VERIFICATION =====

@router.post("/verifications/{employer_id}/reject")
def reject_verification(
    employer_id: uuid.UUID,
    request: VerificationApprovalRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Reject verification request"""
    employer = db.query(Employer).filter(Employer.id == employer_id).first()
    if not employer:
        raise HTTPException(status_code=404, detail="Employer not found")
    
    if employer.verification_tier != "DOCUMENT_VERIFIED":
        raise HTTPException(
            status_code=400,
            detail=f"Can only reject DOCUMENT_VERIFIED employers. Current: {employer.verification_tier}"
        )
    
    # Update employer
    employer.verification_tier = "REJECTED"
    employer.verified_by = admin.id
    
    # Append admin notes
    admin_note = f"\n\n❌ REJECTED by {admin.email}\nDate: {datetime.now(timezone.utc).isoformat()}\nReason: {request.admin_notes}"
    employer.verification_notes = (employer.verification_notes or "") + admin_note
    
    db.commit()
    db.refresh(employer)
    
    # TODO: Send rejection email
    
    return {
        "message": "Verification rejected",
        "employer_id": str(employer.id),
        "company_name": employer.company_name,
        "reason": request.admin_notes
    }


# ===== SUSPEND EMPLOYER =====

@router.post("/verifications/{employer_id}/suspend")
def suspend_employer(
    employer_id: uuid.UUID,
    reason: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Suspend employer account"""
    employer = db.query(Employer).filter(Employer.id == employer_id).first()
    if not employer:
        raise HTTPException(status_code=404, detail="Employer not found")
    
    employer.verification_tier = "SUSPENDED"
    employer.trust_score = 0
    
    admin_note = f"\n\n🚫 SUSPENDED by {admin.email}\nDate: {datetime.now(timezone.utc).isoformat()}\nReason: {reason}"
    employer.verification_notes = (employer.verification_notes or "") + admin_note
    
    db.commit()
    
    return {
        "message": "Employer suspended",
        "employer_id": str(employer.id),
        "reason": reason
    }


# ===== STATISTICS =====

@router.get("/stats/verifications")
def get_verification_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get verification statistics"""
    total = db.query(Employer).count()
    pending = db.query(Employer).filter(Employer.verification_tier == "DOCUMENT_VERIFIED").count()
    verified = db.query(Employer).filter(Employer.verification_tier == "FULLY_VERIFIED").count()
    rejected = db.query(Employer).filter(Employer.verification_tier == "REJECTED").count()
    unverified = db.query(Employer).filter(Employer.verification_tier == "UNVERIFIED").count()
    email_verified = db.query(Employer).filter(Employer.verification_tier == "EMAIL_VERIFIED").count()
    suspended = db.query(Employer).filter(Employer.verification_tier == "SUSPENDED").count()
    
    return {
        "total_employers": total,
        "pending_review": pending,
        "verified": verified,
        "rejected": rejected,
        "unverified": unverified,
        "email_verified": email_verified,
        "suspended": suspended,
        "verification_rate": round((verified / total * 100) if total > 0 else 0, 2)
    }

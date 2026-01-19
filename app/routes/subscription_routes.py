from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User, UserRole
from app.models.employer import Employer
from app.models.subscription import (
    SubscriptionTier, 
    SubscriptionStatus, 
    SUBSCRIPTION_PRICING,
    JOB_POSTING_LIMITS
)
from app.schema.employer_verification_schema import (
    VerificationStatusResponse,
    SubscriptionUpgradeRequest
)
from app.utils.security import get_current_user
from app.crud import employer_crud
from datetime import datetime, timedelta, timezone


router = APIRouter(prefix="/subscription", tags=["subscription"])


@router.get("/status", response_model=VerificationStatusResponse)
def get_full_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get complete verification + subscription status with badges"""
    
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can access this")
    
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(status_code=404, detail="Employer profile not found")
    
    # Get limits and perks
    job_limit = employer.get_job_posting_limit()
    remaining = job_limit - employer.active_job_posts_count if job_limit != -1 else -1
    can_post, reason = employer.can_post_job()
    
    # Determine next upgrade
    next_upgrade = None
    upgrade_benefits = None
    
    if employer.verification_tier == "EMAIL_VERIFIED":
        next_upgrade = "Document Verification (Tier 2)"
        upgrade_benefits = f"Increase job limit to {JOB_POSTING_LIMITS[employer.subscription_tier.value]['DOCUMENT_VERIFIED']} posts"
    elif employer.verification_tier == "DOCUMENT_VERIFIED":
        next_upgrade = "Full Verification (Tier 3)"
        upgrade_benefits = f"Increase job limit to {JOB_POSTING_LIMITS[employer.subscription_tier.value]['FULLY_VERIFIED']} posts + Trusted badge"
    elif employer.subscription_tier == SubscriptionTier.FREE:
        next_upgrade = "BASIC Subscription"
        upgrade_benefits = f"Increase to {JOB_POSTING_LIMITS['BASIC'][employer.verification_tier]} jobs + Analytics"
    elif employer.subscription_tier == SubscriptionTier.BASIC:
        next_upgrade = "PREMIUM Subscription"
        upgrade_benefits = "100 job posts + Priority support + Custom branding"
    
    return {
        "employer_id": employer.id,
        "company_name": employer.company_name,
        "company_type": employer.company_type or "REGISTERED",
        
        "verification_tier": employer.verification_tier,
        "tier_number": employer.get_tier_number(),
        "trust_score": employer.trust_score,
        "verified_at": employer.verified_at,
        
        "subscription_tier": employer.subscription_tier.value,
        "subscription_status": employer.subscription_status.value,
        "subscription_expires_at": employer.subscription_expires_at,
        
        "job_posting_limit": job_limit,
        "active_jobs": employer.active_job_posts_count,
        "remaining_jobs": remaining,
        "can_post_job": can_post,
        
        "badges": employer.get_verification_badges(),
        "perks": employer.get_subscription_perks(),
        
        "next_upgrade_available": next_upgrade,
        "upgrade_benefits": upgrade_benefits
    }


@router.get("/pricing")
def get_pricing():
    """Get subscription pricing and limits"""
    
    pricing_with_limits = {}
    
    for tier in ["FREE", "BASIC", "PREMIUM", "BUSINESS"]:
        pricing_with_limits[tier] = {
            "pricing": SUBSCRIPTION_PRICING[tier],
            "job_limits": JOB_POSTING_LIMITS[tier],
            "features": get_tier_features(tier)
        }
    
    return pricing_with_limits


def get_tier_features(tier: str) -> dict:
    """Get features for each tier"""
    features = {
        "FREE": {
            "job_posting": "Limited (2-5 based on verification)",
            "featured_jobs": "0",
            "analytics": "Basic",
            "support": "Community",
            "branding": "JobScape branding"
        },
        "BASIC": {
            "job_posting": "5-15 based on verification",
            "featured_jobs": "1 featured job",
            "analytics": "Standard analytics",
            "support": "Email support",
            "branding": "JobScape branding"
        },
        "PREMIUM": {
            "job_posting": "Up to 100 jobs",
            "featured_jobs": "5 featured jobs",
            "analytics": "Advanced analytics + AI insights",
            "support": "Priority support (24h response)",
            "branding": "Custom company branding"
        },
        "BUSINESS": {
            "job_posting": "Unlimited",
            "featured_jobs": "Unlimited featured jobs",
            "analytics": "Enterprise analytics + API access",
            "support": "Dedicated account manager",
            "branding": "Full white-label option"
        }
    }
    return features.get(tier, {})


@router.post("/upgrade")
def upgrade_subscription(
    request: SubscriptionUpgradeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Request subscription upgrade"""
    
    if current_user.role != UserRole.EMPLOYER:
        raise HTTPException(status_code=403, detail="Only employers can upgrade")
    
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(status_code=404, detail="Employer profile not found")
    
    # Validate tier
    try:
        new_tier = SubscriptionTier[request.subscription_tier.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail="Invalid subscription tier")
    
    if new_tier == SubscriptionTier.FREE:
        raise HTTPException(status_code=400, detail="Cannot downgrade to FREE")
    
    # Get pricing
    pricing = SUBSCRIPTION_PRICING[new_tier.value]
    amount = pricing["yearly"] if request.billing_cycle == "yearly" else pricing["monthly"]
    
    # TODO: Integrate payment gateway (bKash/Nagad/SSLCommerz)
    # For now, mark as PENDING
    
    employer.subscription_status = SubscriptionStatus.PENDING
    db.commit()
    
    return {
        "message": "Upgrade request received",
        "subscription_tier": new_tier.value,
        "billing_cycle": request.billing_cycle,
        "amount": amount,
        "currency": "BDT",
        "status": "PENDING",
        "payment_instructions": "Payment link will be sent to your email",
        "payment_methods": ["bKash", "Nagad", "Rocket", "Bank Transfer", "Card"]
    }


@router.post("/cancel")
def cancel_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cancel subscription (reverts to FREE at end of period)"""
    
    employer = employer_crud.get_employer_by_user_id(db, current_user.id)
    if not employer:
        raise HTTPException(status_code=404, detail="Employer profile not found")
    
    if employer.subscription_tier == SubscriptionTier.FREE:
        raise HTTPException(status_code=400, detail="Already on FREE tier")
    
    # Don't cancel immediately - wait until expiry
    employer.subscription_status = SubscriptionStatus.CANCELLED
    
    db.commit()
    
    return {
        "message": "Subscription will be cancelled at end of billing period",
        "remains_active_until": employer.subscription_expires_at,
        "reverts_to": "FREE"
    }

from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class VerificationStatusResponse(BaseModel):
    """Detailed verification status with badges"""
    
    # Basic Info
    employer_id: UUID
    company_name: str
    company_type: str  # REGISTERED or STARTUP
    
    # Verification
    verification_tier: str
    tier_number: int
    trust_score: int
    verified_at: Optional[datetime]
    
    # Subscription
    subscription_tier: str
    subscription_status: str
    subscription_expires_at: Optional[datetime]
    
    # Job Posting
    job_posting_limit: int  # -1 = unlimited
    active_jobs: int
    remaining_jobs: int  # -1 = unlimited
    can_post_job: bool
    
    # Badges
    badges: list[str]
    
    # Perks
    perks: dict
    
    # Next Steps
    next_upgrade_available: Optional[str]
    upgrade_benefits: Optional[str]
    
    model_config = {"from_attributes": True}


class SubscriptionUpgradeRequest(BaseModel):
    """Request to upgrade subscription"""
    subscription_tier: str  # BASIC, PREMIUM, BUSINESS
    billing_cycle: str  # monthly, yearly
    payment_method: str  # bkash, nagad, card, bank

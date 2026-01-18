import uuid
from typing import List, Optional
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, DateTime, func, Text, Integer, Float, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.user import User
from app.models.job import Job
from app.models.subscription import SubscriptionTier, SubscriptionStatus


class Employer(Base):
    __tablename__ = "employers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    # Person Info
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    job_title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    work_email: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    # Company Info

    company_name: Mapped[str] = mapped_column(String, nullable=False)
    company_email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    company_website: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    industry: Mapped[str] = mapped_column(String, nullable=False)
    company_size: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    location: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Verification
    verification_tier: Mapped[str] = mapped_column(String, nullable=False, default="UNVERIFIED")
    company_type: Mapped[str] = mapped_column(String, nullable=False, default="REGISTERED")
    is_startup: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    startup_stage: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    founded_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    rjsc_registration_number: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True)
    trade_license_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tin_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    verification_documents: Mapped[List[dict]] = mapped_column(JSONB, default=list, nullable=False)
    verification_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    verified_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    alternative_verification_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    alternative_verification_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    
    document_ai_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    document_ai_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    trust_score: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    reported_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    profile_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # ===== RELATIONSHIPS =====
    # ✅ SPECIFY foreign_keys TO AVOID AMBIGUITY
    user: Mapped["User"] = relationship(
        "User",
        back_populates="employer_profile",
        foreign_keys=[user_id]  # ← LIST FORMAT!
    )

    jobs = relationship(
        "Job",
        back_populates="employer",
        cascade="all, delete-orphan"
    )

    def get_tier_number(self) -> int:
        """Convert tier string to number"""
        tier_map = {
            "UNVERIFIED": 0,
            "EMAIL_VERIFIED": 1,
            "DOCUMENT_VERIFIED": 2,
            "FULLY_VERIFIED": 3,
            "REJECTED": 0,
            "SUSPENDED": 0
        }
        return tier_map.get(self.verification_tier, 0)
    
    def get_verification_badges(self) -> list[str]:
        """Get verification badges based on tier"""
        badges = []
        
        tier = self.verification_tier
        
        # Tier 1: Email Verified
        if tier in ["EMAIL_VERIFIED", "DOCUMENT_VERIFIED", "FULLY_VERIFIED"]:
            badges.append("Email Verified")
        
        # Tier 2: Document Verified
        if tier in ["DOCUMENT_VERIFIED", "FULLY_VERIFIED"]:
            if self.company_type == "REGISTERED":
                badges.append("RJSC Verified")
            elif self.company_type == "STARTUP":
                badges.append("Startup Verified")
            else:
                badges.append("Document Verified")
        
        # Tier 3: Fully Verified (Trusted)
        if tier == "FULLY_VERIFIED":
            badges.append("Trusted Employer ⭐")
        
        # Subscription status
        if self.subscription_tier and self.subscription_status == "ACTIVE":
            if self.subscription_tier == "PREMIUM":
                badges.append("Premium Subscriber 💎")
            elif self.subscription_tier == "BUSINESS":
                badges.append("Business Subscriber 🚀")
        
        # Additional trust indicators
        if self.trust_score >= 90:
            badges.append("High Trust Score")
        
        return badges
    
    # SUBSCRIPTION FIELDS
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        SQLEnum(SubscriptionTier, name="subscription_tier_enum"),
        default=SubscriptionTier.FREE,
        nullable=False
    )
    subscription_status: Mapped[SubscriptionStatus] = mapped_column(
        SQLEnum(SubscriptionStatus, name="subscription_status_enum"),
        default=SubscriptionStatus.ACTIVE,
        nullable=False
    )
    subscription_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    subscription_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Job posting tracking
    active_job_posts_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_job_posts_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # ... rest of existing fields ...
    
    def get_job_posting_limit(self) -> int:
        """Get current job posting limit based on subscription + verification tier"""
        from app.models.subscription import JOB_POSTING_LIMITS
        
        sub_tier = self.subscription_tier.value if self.subscription_tier else "FREE"
        ver_tier = self.verification_tier if self.verification_tier else "UNVERIFIED"
        
        limit = JOB_POSTING_LIMITS.get(sub_tier, {}).get(ver_tier, 0)
        return limit
    
    def can_post_job(self) -> tuple[bool, str]:
        """Check if employer can post a new job"""
        # Check subscription status
        if self.subscription_status != SubscriptionStatus.ACTIVE:
            return False, "Subscription is not active"
        
        # Check verification tier
        if self.verification_tier == "UNVERIFIED":
            return False, "Please verify your email first"
        
        if self.verification_tier == "SUSPENDED":
            return False, "Account is suspended"
        
        if self.verification_tier == "REJECTED":
            return False, "Verification was rejected. Please contact support"
        
        # Get limit
        limit = self.get_job_posting_limit()
        
        # -1 means unlimited
        if limit == -1:
            return True, "Unlimited job postings"
        
        # Check if under limit
        if self.active_job_posts_count < limit:
            return True, f"Can post ({self.active_job_posts_count}/{limit} used)"
        else:
            return False, f"Job posting limit reached ({self.active_job_posts_count}/{limit}). Upgrade subscription or verification tier."
    
    def get_subscription_perks(self) -> dict:
        """Get perks based on subscription tier"""
        perks = {
            "FREE": {
                "featured_jobs": 0,
                "priority_support": False,
                "analytics": "Basic",
                "application_tracking": False,
                "custom_branding": False
            },
            "BASIC": {
                "featured_jobs": 1,
                "priority_support": False,
                "analytics": "Standard",
                "application_tracking": True,
                "custom_branding": False
            },
            "PREMIUM": {
                "featured_jobs": 5,
                "priority_support": True,
                "analytics": "Advanced",
                "application_tracking": True,
                "custom_branding": True
            },
            "BUSINESS": {
                "featured_jobs": -1,  # Unlimited
                "priority_support": True,
                "analytics": "Enterprise",
                "application_tracking": True,
                "custom_branding": True,
                "dedicated_account_manager": True
            }
        }
        
        tier = self.subscription_tier.value if self.subscription_tier else "FREE"
        return perks.get(tier, perks["FREE"])

# app/models/employer.py
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

    # ==================== PRIMARY KEYS ====================

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

    # ==================== PERSON INFO ====================

    full_name: Mapped[str] = mapped_column(String, nullable=False)
    job_title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    work_email: Mapped[str] = mapped_column(String, nullable=True, unique=True)

    # Work Email Verification (NEW - Added for security)
    work_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    work_email_verification_token: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    work_email_verification_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    work_email_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # ==================== COMPANY INFO ====================

    company_name: Mapped[str] = mapped_column(String, nullable=False)
    company_email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    company_website: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    industry: Mapped[str] = mapped_column(String, nullable=True)
    company_size: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    location: Mapped[str] = mapped_column(String, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    cloudinary_public_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # ==================== VERIFICATION SYSTEM ====================

    # Verification Tier (UNVERIFIED → EMAIL_VERIFIED → DOCUMENT_VERIFIED → FULLY_VERIFIED)
    verification_tier: Mapped[str] = mapped_column(String, nullable=False, default="UNVERIFIED")

    # Company Type
    company_type: Mapped[str] = mapped_column(String, nullable=False, default="REGISTERED")
    is_startup: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    startup_stage: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    founded_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Registration Documents
    rjsc_registration_number: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True)
    trade_license_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tin_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Document Storage
    verification_documents: Mapped[List[dict]] = mapped_column(JSONB, default=list, nullable=False)
    verification_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    # Alternative Verification (for startups/freelancers)
    alternative_verification_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    alternative_verification_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # AI Document Verification
    document_ai_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    document_ai_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Trust System
    trust_score: Mapped[int] = mapped_column(Integer, default=20, nullable=False)  # Changed default from 50 to 20
    reported_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ==================== SUBSCRIPTION SYSTEM ====================

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

    # ==================== JOB POSTING TRACKING ====================

    active_job_posts_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_job_posts_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ==================== METADATA ====================

    profile_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # ==================== RELATIONSHIPS ====================

    user: Mapped["User"] = relationship(
        "User",
        back_populates="employer_profile",
        foreign_keys=[user_id]
    )

    jobs = relationship(
        "Job",
        back_populates="employer",
        cascade="all, delete-orphan"
    )

    # ==================== METHODS ====================

    def get_tier_number(self) -> int:
        """
        Convert verification tier string to number for comparisons

        Returns:
            0 = UNVERIFIED/REJECTED/SUSPENDED
            1 = EMAIL_VERIFIED
            2 = DOCUMENT_VERIFIED
            3 = FULLY_VERIFIED
        """
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
        """
        Get list of verification badges to display on profile/jobs

        Returns:
            List of badge strings (e.g., ["Email Verified", "RJSC Verified"])
        """
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

        # Subscription badges
        if self.subscription_tier and self.subscription_status == SubscriptionStatus.ACTIVE:
            if self.subscription_tier == SubscriptionTier.PREMIUM:
                badges.append("Premium Subscriber 💎")
            elif self.subscription_tier == SubscriptionTier.BUSINESS:
                badges.append("Business Subscriber 🚀")

        # Trust score badge
        if self.trust_score >= 90:
            badges.append("High Trust Score")

        return badges

    def get_job_posting_limit(self) -> int:
        """
        Get current job posting limit based on subscription + verification tier

        Returns:
            -1 for unlimited, otherwise the number of jobs allowed
        """
        from app.models.subscription import JOB_POSTING_LIMITS

        sub_tier = self.subscription_tier.value if self.subscription_tier else "FREE"
        ver_tier = self.verification_tier if self.verification_tier else "UNVERIFIED"

        limit = JOB_POSTING_LIMITS.get(sub_tier, {}).get(ver_tier, 0)
        return limit

    def can_post_job(self) -> tuple[bool, str]:
        """
        Check if employer can post a new job

        Returns:
            Tuple of (can_post: bool, reason: str)
        """
        # Check subscription status
        if self.subscription_status != SubscriptionStatus.ACTIVE:
            return False, "Subscription is not active"

        # Check verification tier
        if self.verification_tier == "UNVERIFIED":
            return False, "Please verify your work email first"

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
            remaining = limit - self.active_job_posts_count
            return True, f"Can post ({remaining} remaining out of {limit})"
        else:
            return False, f"Job posting limit reached ({self.active_job_posts_count}/{limit}). Upgrade subscription or verification tier."

    def get_subscription_perks(self) -> dict:
        """
        Get perks/features available for current subscription tier

        Returns:
            Dictionary of perks and their values
        """
        perks = {
            "FREE": {
                "job_posting_limit_multiplier": 1.0,
                "featured_jobs": 0,
                "priority_support": False,
                "analytics": "Basic",
                "application_tracking": False,
                "custom_branding": False,
                "api_access": False,
                "bulk_posting": False
            },
            "BASIC": {
                "job_posting_limit_multiplier": 1.5,
                "featured_jobs": 1,
                "priority_support": False,
                "analytics": "Standard",
                "application_tracking": True,
                "custom_branding": False,
                "api_access": False,
                "bulk_posting": False
            },
            "PREMIUM": {
                "job_posting_limit_multiplier": 2.0,
                "featured_jobs": 5,
                "priority_support": True,
                "analytics": "Advanced",
                "application_tracking": True,
                "custom_branding": True,
                "api_access": True,
                "bulk_posting": True
            },
            "BUSINESS": {
                "job_posting_limit_multiplier": -1,  # Unlimited
                "featured_jobs": -1,  # Unlimited
                "priority_support": True,
                "analytics": "Enterprise",
                "application_tracking": True,
                "custom_branding": True,
                "api_access": True,
                "bulk_posting": True,
                "dedicated_account_manager": True,
                "white_label": True
            }
        }

        tier = self.subscription_tier.value if self.subscription_tier else "FREE"
        return perks.get(tier, perks["FREE"])

    def increment_job_counter(self):
        """Increment job posting counters when a new job is posted"""
        self.active_job_posts_count += 1
        self.total_job_posts_count += 1

    def decrement_job_counter(self):
        """Decrement active job counter when a job is closed/deleted"""
        if self.active_job_posts_count > 0:
            self.active_job_posts_count -= 1

    def __repr__(self):
        return f"<Employer(id={self.id}, company={self.company_name}, tier={self.verification_tier})>"
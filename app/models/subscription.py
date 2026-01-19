import uuid
import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Boolean, ForeignKey, Enum as SQLEnum, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class SubscriptionTier(str, enum.Enum):
    """Subscription tiers for employers"""
    FREE = "FREE"
    BASIC = "BASIC"
    PREMIUM = "PREMIUM"
    BUSINESS = "BUSINESS"


class SubscriptionStatus(str, enum.Enum):
    """Subscription status"""
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    PENDING = "PENDING"


# Job Posting Limits per tier
JOB_POSTING_LIMITS = {
    "FREE": {
        "UNVERIFIED": 0,           # Can't post until email verified
        "EMAIL_VERIFIED": 2,        # Tier 1: 2 jobs max
        "DOCUMENT_VERIFIED": 3,     # Tier 2: 3 jobs max
        "FULLY_VERIFIED": 5         # Tier 3: 5 jobs max
    },
    "BASIC": {
        "UNVERIFIED": 0,
        "EMAIL_VERIFIED": 5,
        "DOCUMENT_VERIFIED": 10,
        "FULLY_VERIFIED": 15
    },
    "PREMIUM": {
        "UNVERIFIED": 0,
        "EMAIL_VERIFIED": 20,
        "DOCUMENT_VERIFIED": 50,
        "FULLY_VERIFIED": 100       # Premium + Fully Verified = 100 jobs
    },
    "BUSINESS": {
        "UNVERIFIED": 0,
        "EMAIL_VERIFIED": 50,
        "DOCUMENT_VERIFIED": 150,
        "FULLY_VERIFIED": -1        # -1 = UNLIMITED
    }
}


# Subscription pricing (in BDT)
SUBSCRIPTION_PRICING = {
    "FREE": {"monthly": 0, "yearly": 0},
    "BASIC": {"monthly": 2000, "yearly": 20000},      # ~$20/month
    "PREMIUM": {"monthly": 5000, "yearly": 50000},    # ~$50/month
    "BUSINESS": {"monthly": 15000, "yearly": 150000}  # ~$150/month
}

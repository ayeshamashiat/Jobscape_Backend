import re
from typing import Tuple
import dns.resolver


# Blocked free email providers
BLOCKED_DOMAINS = [
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
    "mail.com", "protonmail.com", "icloud.com", "aol.com",
    "zoho.com", "yandex.com", "gmx.com"
]


def verify_work_email_ownership(email: str, company_website: str) -> Tuple[bool, str]:
    """
    Verify that email domain matches company website.
    NO MX record validation - accepts any domain.
    
    Returns:
        (is_valid, error_message)
    """
    email_lower = email.lower().strip()
    email_domain = email_lower.split("@")[-1]
    
    # CHECK 1: Not a free email provider
    email_base = '.'.join(email_domain.split('.')[-2:])
    if email_base in BLOCKED_DOMAINS:
        return False, f"Please use your company email, not {email_base}"
    
    # Extract company domain from website
    website_clean = company_website.lower().strip()
    website_clean = re.sub(r'^(https?://)?(www\.)?', '', website_clean)
    website_domain = website_clean.split('/')[0]
    
    # Get base domains
    website_base = '.'.join(website_domain.split('.')[-2:])
    
    # CHECK 2: Domains must match
    if email_base != website_base:
        return False, f"Email domain ({email_domain}) doesn't match company website ({website_domain})"
    
    # ✅ REMOVED CHECK 3 - No MX record validation
    # Accept any domain as long as it's not blocked and matches website
    
    return True, "Valid"

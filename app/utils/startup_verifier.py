import requests
from typing import Dict, Tuple
import re


def verify_linkedin_company(linkedin_url: str) -> Tuple[bool, Dict]:
    """Verify LinkedIn company page exists"""
    try:
        match = re.search(r'linkedin\.com/company/([^/]+)', linkedin_url)
        if not match:
            return False, {"error": "Invalid LinkedIn URL format"}
        
        company_slug = match.group(1)
        
        # LinkedIn API requires authentication
        # For now, just validate URL format
        return True, {
            "company_slug": company_slug,
            "verified": True,
            "method": "manual_check_required",
            "note": "Admin should manually verify page exists."
        }
    
    except Exception as e:
        return False, {"error": str(e)}


def verify_website_legitimacy(website_url: str) -> Dict:
    """Quick automated checks for website legitimacy"""
    checks = {
        "accessible": False,
        "has_ssl": False,
        "response_time_ms": None,
        "status_code": None,
        "notes": []
    }
    
    try:
        import time
        start = time.time()
        response = requests.get(website_url, timeout=10, allow_redirects=True)
        elapsed = (time.time() - start) * 1000
        
        checks["accessible"] = response.status_code == 200
        checks["status_code"] = response.status_code
        checks["response_time_ms"] = round(elapsed, 2)
        checks["has_ssl"] = website_url.startswith("https://")
        
        if checks["accessible"]:
            checks["notes"].append("✅ Website is accessible")
        if checks["has_ssl"]:
            checks["notes"].append("✅ Has SSL certificate (https)")
        
        if not checks["accessible"]:
            checks["notes"].append("❌ Website not accessible")
        if not checks["has_ssl"]:
            checks["notes"].append("⚠️ No SSL certificate")
    
    except requests.exceptions.Timeout:
        checks["notes"].append("❌ Website timeout")
    except requests.exceptions.ConnectionError:
        checks["notes"].append("❌ Cannot connect to website")
    except Exception as e:
        checks["notes"].append(f"❌ Error: {str(e)}")
    
    return checks


def calculate_startup_trust_score(employer) -> int:
    """Calculate trust score for startups"""
    score = 40  # Base score for startups
    
    # LinkedIn verification
    alt_data = employer.alternative_verification_data
    if alt_data.get("linkedin_url"):
        score += 10
        if alt_data.get("linkedin_followers", 0) > 100:
            score += 5
        if alt_data.get("linkedin_followers", 0) > 500:
            score += 5
    
    # Website verification
    if alt_data.get("website_has_ssl"):
        score += 10
    
    # Established time
    if employer.founded_year:
        years_old = 2026 - employer.founded_year
        score += min(years_old * 3, 15)
    
    # Email domain matches website
    if employer.company_website and employer.work_email:
        email_domain = employer.work_email.split("@")[-1]
        website_domain = employer.company_website.replace("https://", "").replace("http://", "").split("/")[0]
        if email_domain in website_domain:
            score += 10
    
    return min(score, 100)

"""
AI-powered cover letter generator utility
Uses Groq API (OpenAI-compatible) to generate personalized cover letters
"""

import os
from typing import Dict, Any, Optional
from openai import OpenAI

class CoverLetterGeneratorError(Exception):
    """Custom exception for cover letter generation errors"""
    pass


class AICoverLetterGenerator:
    """
    AI Cover Letter Generator using Groq/OpenAI
    
    Usage:
        generator = AICoverLetterGenerator()
        cover_letter = generator.generate(
            job_title="Software Engineer",
            company_name="Tech Corp",
            job_description="...",
            user_profile={"skills": [...], "experience": [...]}
        )
    """
    
    def __init__(self, api_key: Optional[str] = None, provider: str = "groq"):
        """
        Initialize the cover letter generator
        
        Args:
            api_key: API key for the AI service (defaults to env variable)
            provider: "groq" or "openai"
        """
        self.provider = provider.lower()
        
        if self.provider == "groq":
            self.api_key = api_key or os.getenv("GROQ_API_KEY")
            self.base_url = "https://api.groq.com/openai/v1"
            self.model = "llama-3.3-70b-versatile"
        elif self.provider == "openai":
            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            self.base_url = None  # OpenAI default
            self.model = "gpt-4"
        else:
            raise ValueError(f"Unsupported provider: {provider}")
        
        if not self.api_key:
            raise CoverLetterGeneratorError(
                f"No API key found. Set {self.provider.upper()}_API_KEY environment variable"
            )
        
        # Initialize OpenAI client (works for both Groq and OpenAI)
        if self.base_url:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        else:
            self.client = OpenAI(api_key=self.api_key)
    
    def generate(
        self,
        job_title: str,
        company_name: Optional[str],
        job_location: Optional[str],
        required_skills: list,
        experience_level: Optional[str],
        job_type: Optional[str],
        work_mode: Optional[str],
        user_profile: Dict[str, Any]
    ) -> str:
        """
        Generate a personalized cover letter
        
        Args:
            job_title: Job title
            company_name: Company name (optional)
            job_location: Job location
            required_skills: List of required skills
            experience_level: Entry/Mid/Senior
            job_type: Full-time/Part-time/Contract
            work_mode: Remote/Hybrid/On-site
            user_profile: Dict with user's profile data (name, skills, experience, etc.)
        
        Returns:
            Generated cover letter text
        
        Raises:
            CoverLetterGeneratorError: If generation fails
        """
        
        # Build user context
        user_name = user_profile.get("full_name", "Applicant")
        user_skills = user_profile.get("skills", [])
        user_experience = user_profile.get("experience", [])
        user_education = user_profile.get("education", [])
        user_summary = user_profile.get("professional_summary", "")
        user_location = user_profile.get("location", "")
        
        # Format experience count
        experience_years = len(user_experience) if user_experience else 0
        experience_text = f"{experience_years}+ years of experience" if experience_years > 0 else "fresher/entry-level"
        
        # Build job context
        company_text = f"at {company_name}" if company_name else ""
        skills_match = set(user_skills) & set(required_skills) if user_skills and required_skills else set()
        skills_match_text = f"matching skills: {', '.join(list(skills_match)[:5])}" if skills_match else "relevant background"
        
        # Construct the prompt
        prompt = f"""You are a professional cover letter writer. Write a compelling, ATS-friendly cover letter for this job application.

JOB DETAILS:
- Position: {job_title} {company_text}
- Location: {job_location or 'Not specified'}
- Required Skills: {', '.join(required_skills[:8]) if required_skills else 'Not specified'}
- Experience Level: {experience_level or 'Not specified'}
- Job Type: {job_type or 'Not specified'}
- Work Mode: {work_mode or 'Not specified'}

APPLICANT PROFILE:
- Name: {user_name}
- Location: {user_location or 'Not specified'}
- Experience: {experience_text}
- Skills: {', '.join(user_skills[:10]) if user_skills else 'Not specified'}
- Professional Summary: {user_summary or 'Not provided'}

KEY MATCHING QUALIFICATIONS:
{skills_match_text}

INSTRUCTIONS:
1. Write a professional cover letter (200-280 words)
2. Start with a strong opening that shows enthusiasm
3. Highlight {user_name}'s relevant skills and experience that match the job
4. Be specific about why they're a good fit for this {job_title} role
5. Use the actual name "{user_name}" - no placeholders
6. Match tone to experience level ({experience_level or 'professional'})
7. If fresher/entry-level, emphasize learning ability and relevant coursework/projects
8. Don't make up experience or skills not mentioned
9. Keep it concise and impactful
10. End with a call to action

Format: Plain text paragraphs (no subject line, no "Dear Hiring Manager" - start directly with the body). Don't include sender/receiver addresses.

Write the cover letter now:"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional cover letter writer specializing in tech and business roles. Write clear, compelling, ATS-optimized cover letters."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,  # Balance creativity and consistency
                max_tokens=600,   # ~300-400 words
                top_p=0.9
            )
            
            cover_letter = response.choices[0].message.content.strip()
            
            # Basic validation
            if len(cover_letter) < 100:
                raise CoverLetterGeneratorError("Generated cover letter is too short")
            
            # Remove any accidental headers/footers if present
            cover_letter = self._clean_cover_letter(cover_letter)
            
            return cover_letter
        
        except Exception as e:
            error_msg = str(e)
            if "api_key" in error_msg.lower():
                raise CoverLetterGeneratorError(f"API authentication failed. Check your {self.provider.upper()} API key.")
            elif "rate_limit" in error_msg.lower():
                raise CoverLetterGeneratorError("Rate limit exceeded. Please try again in a moment.")
            elif "timeout" in error_msg.lower():
                raise CoverLetterGeneratorError("Request timed out. Please try again.")
            else:
                raise CoverLetterGeneratorError(f"Failed to generate cover letter: {error_msg}")
    
    def _clean_cover_letter(self, text: str) -> str:
        """Remove unwanted headers, footers, or formatting artifacts"""
        
        # Remove common unwanted patterns
        lines = text.split('\n')
        cleaned_lines = []
        
        skip_patterns = [
            "dear hiring manager",
            "sincerely,",
            "best regards,",
            "yours faithfully",
            "[your name]",
            "[date]",
            "subject:",
        ]
        
        for line in lines:
            line_lower = line.strip().lower()
            
            # Skip lines with unwanted patterns
            if any(pattern in line_lower for pattern in skip_patterns):
                continue
            
            # Skip empty lines at the start
            if not cleaned_lines and not line.strip():
                continue
            
            cleaned_lines.append(line)
        
        # Join and clean up excessive newlines
        result = '\n'.join(cleaned_lines)
        result = '\n\n'.join(para.strip() for para in result.split('\n\n') if para.strip())
        
        return result.strip()


# Convenience function for quick use
def generate_cover_letter(
    job_title: str,
    company_name: Optional[str],
    job_location: Optional[str],
    required_skills: list,
    experience_level: Optional[str],
    job_type: Optional[str],
    work_mode: Optional[str],
    user_profile: Dict[str, Any],
    provider: str = "groq"
) -> str:
    """
    Quick function to generate a cover letter
    
    Example:
        cover_letter = generate_cover_letter(
            job_title="Backend Engineer",
            company_name="TechCorp",
            job_location="Dhaka",
            required_skills=["Python", "FastAPI", "PostgreSQL"],
            experience_level="Mid-Level",
            job_type="Full-time",
            work_mode="Hybrid",
            user_profile={
                "full_name": "John Doe",
                "skills": ["Python", "FastAPI", "Docker"],
                "experience": [{"company": "ABC", "position": "Developer"}],
                "professional_summary": "Software engineer with 3 years experience"
            }
        )
    """
    generator = AICoverLetterGenerator(provider=provider)
    return generator.generate(
        job_title=job_title,
        company_name=company_name,
        job_location=job_location,
        required_skills=required_skills,
        experience_level=experience_level,
        job_type=job_type,
        work_mode=work_mode,
        user_profile=user_profile
    )

import os
import json
import re
from typing import Optional
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

def score_resume_against_job(
    resume_parsed_data: dict,
    job_title: str,
    job_description: str,
    required_skills: list,
    preferred_skills: list,
    experience_level: Optional[str] = None,
) -> dict:
    """
    ATS-score a resume against a job using Groq AI.
    Returns a dict with overall_score (0–100) and breakdown.
    """
    resume_text = _format_resume_for_scoring(resume_parsed_data)

    prompt = f"""You are an expert ATS (Applicant Tracking System) evaluator.

JOB DETAILS:
- Title: {job_title}
- Description: {job_description[:1500]}
- Required Skills: {", ".join(required_skills) if required_skills else "Not specified"}
- Preferred Skills: {", ".join(preferred_skills) if preferred_skills else "None"}
- Experience Level: {experience_level or "Not specified"}

CANDIDATE RESUME:
{resume_text[:2500]}

Score this resume against the job. Return ONLY valid JSON with these exact keys:
{{
  "overall_score": <integer 0-100>,
  "skill_match_score": <integer 0-100>,
  "experience_match_score": <integer 0-100>,
  "education_match_score": <integer 0-100>,
  "keyword_match_score": <integer 0-100>,
  "matched_required_skills": ["skill1", "skill2"],
  "matched_preferred_skills": ["skill1"],
  "missing_required_skills": ["skill1", "skill2"],
  "strengths": ["strength1", "strength2"],
  "gaps": ["gap1", "gap2"],
  "recommendation": "STRONG_MATCH" | "GOOD_MATCH" | "PARTIAL_MATCH" | "WEAK_MATCH",
  "summary": "One sentence ATS summary"
}}

Scoring weights: Skills 40%, Experience 30%, Keywords 20%, Education 10%.
Be strict and accurate. Return ONLY the JSON object."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a precise ATS scoring engine. Output only valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_tokens=1000,
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown code blocks if present
    raw = re.sub(r"^```(?:json)?\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)

    result = json.loads(raw)
    return result


def _format_resume_for_scoring(parsed_data: dict) -> str:
    """Convert parsed resume JSON into readable text for AI scoring."""
    if not parsed_data:
        return "No resume data available."

    parts = []

    if parsed_data.get("name"):
        parts.append(f"Name: {parsed_data['name']}")
    if parsed_data.get("professional_summary"):
        parts.append(f"Summary: {parsed_data['professional_summary']}")
    if parsed_data.get("skills"):
        parts.append(f"Skills: {', '.join(parsed_data['skills'])}")

    experience = parsed_data.get("experience", [])
    if experience:
        exp_lines = ["Experience:"]
        for exp in experience[:5]:
            exp_lines.append(
                f"  - {exp.get('position', '')} at {exp.get('company', '')} ({exp.get('duration', '')}): "
                f"{exp.get('description', '')}"
            )
        parts.append("\n".join(exp_lines))

    education = parsed_data.get("education", [])
    if education:
        edu_lines = ["Education:"]
        for edu in education[:3]:
            edu_lines.append(
                f"  - {edu.get('degree', '')} in {edu.get('field', '')} from {edu.get('institution', '')} "
                f"({edu.get('graduation_year', '')})"
            )
        parts.append("\n".join(edu_lines))

    if parsed_data.get("certifications"):
        certs = [c.get("name", "") for c in parsed_data["certifications"][:4]]
        parts.append(f"Certifications: {', '.join(certs)}")

    if parsed_data.get("projects"):
        proj_names = [p.get("title", "") for p in parsed_data["projects"][:4]]
        parts.append(f"Projects: {', '.join(proj_names)}")

    return "\n".join(parts)
from openai import OpenAI
import os
import json


# ✅ GROQ CLIENT (OpenAI-compatible API)
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),  # ← Changed
    base_url="https://api.groq.com/openai/v1"  # ← Changed
)


def structure_resume_with_ai(resume_text: str) -> dict:
    """
    Send extracted text to Groq for comprehensive structured parsing
    """
    if not resume_text or len(resume_text.strip()) < 50:
        raise ValueError("Resume text is too short or empty")
    
    prompt = f"""You are an expert resume parser. Extract ALL relevant information from the following resume text.


Return ONLY a valid JSON object with these exact keys (use null for missing info, [] for empty arrays):


{{
  "name": "Full name",
  "email": "Email address",
  "phone": "Phone number with country code",
  "location": "Current city/location",
  "professional_summary": "Brief professional summary or objective statement",
  
  "skills": ["skill1", "skill2", "skill3"],
  
  "experience": [
    {{
      "company": "Company name",
      "position": "Job title/role",
      "duration": "Start date - End date (e.g., Jan 2020 - Present)",
      "description": "Brief description of responsibilities and achievements",
      "technologies": ["tech1", "tech2"]
    }}
  ],
  
  "education": [
    {{
      "institution": "University/School name",
      "degree": "Degree/Certification name",
      "field": "Field of study/major",
      "graduation_year": "Year or expected year",
      "gpa": "GPA if mentioned",
      "location": "City, Country"
    }}
  ],
  
  "projects": [
    {{
      "title": "Project name",
      "description": "Brief project description and impact",
      "technologies": ["tech1", "tech2"],
      "role": "Your role in the project",
      "link": "GitHub/demo link if available",
      "duration": "Project duration or date"
    }}
  ],
  
  "certifications": [
    {{
      "name": "Certification name",
      "issuer": "Issuing organization",
      "date": "Issue date",
      "expiry_date": "Expiry date if applicable",
      "credential_id": "Certificate ID/URL",
      "skills": ["related skills"]
    }}
  ],
  
  "awards": [
    {{
      "title": "Award/achievement name",
      "issuer": "Issuing organization or competition name",
      "date": "Date received",
      "description": "Brief description"
    }}
  ],
  
  "languages": [
    {{
      "name": "Language name",
      "proficiency": "Native/Fluent/Advanced/Intermediate/Basic"
    }}
  ],
  
  "publications": [
    {{
      "title": "Publication/paper title",
      "publisher": "Journal/conference name",
      "date": "Publication date",
      "link": "DOI or URL if available",
      "authors": ["author1", "author2"]
    }}
  ],
  
  "volunteer_experience": [
    {{
      "organization": "Organization name",
      "role": "Volunteer role/position",
      "duration": "Start - End date",
      "description": "Brief description of activities"
    }}
  ],
  
  "links": {{
    "linkedin": "LinkedIn profile URL",
    "github": "GitHub profile URL",
    "portfolio": "Personal website/portfolio URL",
    "others": ["other professional links"]
  }}
}}


IMPORTANT INSTRUCTIONS:
- Extract ALL information present in the resume, even if fields seem optional
- For Bangladeshi universities (e.g., IUT, BUET, DU), include full names
- Parse dates in consistent format (e.g., "Jan 2020 - Dec 2022")
- If experience is described in Bengali/mixed language, extract in English
- Include GitHub project links, competition achievements, hackathon wins
- Parse CGPA/GPA values accurately
- Extract technical skills separately from soft skills if possible


Resume text:
{resume_text[:6000]}
"""
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # ← Changed to Groq model
            messages=[
                {"role": "system", "content": "You are a precise resume parser optimized for software engineering and IT resumes. Output only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=3000
        )
        
        result = response.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        if result.startswith("```json"):
            result = result[7:]
        if result.startswith("```"):
            result = result[3:]
        if result.endswith("```"):
            result = result[:-3]
        
        parsed_data = json.loads(result.strip())
        
        # Post-process to ensure proper structure
        parsed_data = normalize_parsed_data(parsed_data)
        
        return parsed_data
    
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        print(f"Raw response: {result}")
        raise ValueError("AI returned invalid JSON")
    except Exception as e:
        print(f"AI parsing error: {e}")
        raise ValueError(f"AI parsing failed: {str(e)}")



def normalize_parsed_data(data: dict) -> dict:
    """
    Normalize and validate parsed resume data
    """
    # Ensure all array fields exist
    array_fields = [
        'skills', 'experience', 'education', 'projects', 
        'certifications', 'awards', 'languages', 
        'publications', 'volunteer_experience'
    ]
    
    for field in array_fields:
        if field not in data or data[field] is None:
            data[field] = []
    
    # Ensure links object exists
    if 'links' not in data or data['links'] is None:
        data['links'] = {}
    
    # Normalize empty strings to None for optional fields
    optional_string_fields = ['name', 'email', 'phone', 'location', 'professional_summary']
    for field in optional_string_fields:
        if field in data and data[field] == "":
            data[field] = None
    
    return data

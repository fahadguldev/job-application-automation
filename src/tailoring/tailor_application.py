import os
import re
import json
from dotenv import load_dotenv

try:
    from core.groq_client import GroqClient
    from tailoring.document_generator import DocumentGenerator
except ImportError:
    from groq_client import GroqClient
    from document_generator import DocumentGenerator

load_dotenv()

TAILOR_APP_SYSTEM_PROMPT = """You are an elite HR Recruiter and Resume Optimizer Specialist.
Your objective is to tailor a candidate's CV for a specific job posting and generate a concise, personalized outreach email message for recruiters/hiring managers.

CRITICAL COMPLIANCE RULES:
1. FACTUAL ACCURACY IS MANDATORY: Do NOT invent skills, fake projects, false companies, unearned certifications, or fake metrics.
2. ALIGNMENT & REORGANIZATION ONLY: Rephrase, reorganize, and emphasize the candidate's real experience to match the target job's keywords and requirements.
3. NO COVER LETTER: Do NOT generate a cover letter. Focus strictly on tailoring the CV and crafting a custom outreach email message.
4. STRUCTURED JSON OUTPUT: You MUST respond strictly with a valid JSON object matching the exact schema below.

JSON OUTPUT SCHEMA:
{
  "tailored_cv": {
    "name": "MUHAMMAD FAHAD",
    "headline": "<tailored target role headline>",
    "contact": "Lahore, Pakistan | devfahad785@gmail.com | +92-3329296026 | devrfgul.vercel.app | linkedin.com/in/fahad785 | github.com/fahadguldev",
    "summary": "<2-3 sentence summary emphasizing job-relevant strengths>",
    "skills": {
      "Languages & Frameworks": ["<skill1>", "<skill2>"],
      "Databases & Backend": ["<skill3>", "<skill4>"],
      "Tools & Methodologies": ["<skill5>", "<skill6>"]
    },
    "experience": [
      {
        "title": "<role title>",
        "company": "<company>",
        "dates": "<dates>",
        "location": "<location>",
        "bullets": ["<bullet 1>", "<bullet 2>"]
      }
    ],
    "projects": [
      {
        "title": "<project name>",
        "link": "<url if any>",
        "tech": "<tech stack>",
        "bullets": ["<bullet 1>", "<bullet 2>"]
      }
    ],
    "education": [
      {
        "degree": "<degree>",
        "institution": "<university>",
        "dates": "<dates>",
        "grade": "<grade/gpa>"
      }
    ]
  },
  "email_outreach": {
    "subject": "Application for <job_title> - Muhammad Fahad",
    "body": "Dear Hiring Team,\\n\\nI came across your job posting for <job_title> at <company_name> and am very eager to express my interest in joining your team.\\n\\nWith hands-on experience in full-stack web engineering, building scalable APIs, and crafting responsive user interfaces, I believe my background aligns strongly with your requirements.\\n\\nI have attached my tailored resume for your review. I would welcome the opportunity to discuss how my technical skills can add value to your projects.\\n\\nBest regards,\\nMuhammad Fahad\\nLahore, Pakistan | devfahad785@gmail.com | +92-3329296026"
  }
}
"""

def sanitize_folder_name(name: str) -> str:
    """Sanitizes text to form a safe directory name."""
    clean = re.sub(r"[^\w\s-]", "", name)
    clean = re.sub(r"[\s-]+", "_", clean).strip("_")
    return clean[:60] if clean else "job_application"

class ApplicationTailor:
    """Generates tailored CV (.pdf & .docx) and custom email outreach text for jobs."""

    def __init__(self, cv_text: str):
        self.cv_text = cv_text
        self.groq_client = GroqClient()

    def generate_application(self, job: dict, base_output_dir: str = "outputs") -> dict:
        company = job.get("company", "Company")
        title = job.get("title", "Software Engineer")
        description = job.get("description", "")
        job_id = job.get("id", "JOB")

        clean_company = sanitize_folder_name(company)
        clean_title = sanitize_folder_name(title)
        folder_name = f"{clean_company}_{clean_title}"
        job_output_dir = os.path.join(base_output_dir, folder_name)

        print(f"\n📂 Generating tailored CV PDF in: {job_output_dir}")

        user_prompt = f"""
Candidate Base Resume:
----------------------------------------
{self.cv_text}
----------------------------------------

Target Job Details:
----------------------------------------
Job Title: {title}
Company Name: {company}
Job Description & Requirements:
{description}
----------------------------------------

Please generate the Tailored CV data and Custom Email Outreach data matching the exact JSON schema provided.
"""

        raw_response = self.groq_client.evaluate(
            system_prompt=TAILOR_APP_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            json_mode=True
        )

        data = json.loads(raw_response)
        cv_data = data.get("tailored_cv", {})
        email_data = data.get("email_outreach", {})

        email_subject = email_data.get("subject", f"Application for {title} - Muhammad Fahad")
        email_body = email_data.get("body", f"Dear Hiring Team,\n\nI am applying for the {title} position at {company}.\n\nBest regards,\nMuhammad Fahad")

        # Create output PDF and DOCX files
        cv_pdf_path = os.path.join(job_output_dir, "tailored_cv.pdf")
        cv_docx_path = os.path.join(job_output_dir, "tailored_cv.docx")

        # 1. tailored_cv.pdf
        DocumentGenerator.create_cv_pdf(cv_data, cv_pdf_path)
        print(f"   ✅ Created PDF CV: {cv_pdf_path}")

        # 2. tailored_cv.docx
        DocumentGenerator.create_cv_docx(cv_data, cv_docx_path)
        print(f"   ✅ Created DOCX CV: {cv_docx_path}")

        return {
            "output_dir": job_output_dir,
            "cv_pdf_path": cv_pdf_path,
            "email_subject": email_subject,
            "email_body": email_body
        }


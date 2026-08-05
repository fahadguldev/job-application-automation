import os
import json
import re
import argparse
from dotenv import load_dotenv
try:
    from core.groq_client import GroqClient
except ImportError:
    from groq_client import GroqClient

load_dotenv()

TAILOR_SYSTEM_PROMPT = """You are an elite ATS Resume Optimization Specialist and LaTeX Expert.
Your task is to tailor a candidate's base LaTeX CV (`main.tex`) for a specific Job Description.

STRICT RULES:
1. PRESERVE LATEX STRUCTURE & MACROS: Keep the exact LaTeX packages, preamble, environment structure, and custom commands intact (e.g. \\leftsection, \\rightsection, \\jobheading, \\projheading, \\cvitems, \\skilltag, \\skillcat).
2. KEYWORD & SKILL ALIGNMENT: Tailor the summary, skill tags, experience bullet points, and project descriptions to emphasize skills, terms, and achievements relevant to the target job.
3. NO FABRICATION: Do NOT invent fake companies, fake degrees, or false experience. Enhance, reorder, and reframe real experiences to highlight maximum job alignment.
4. VALID COMPILEABLE LATEX: Ensure all curly braces, escape characters (e.g. \\%, \\&, \\$), and environments match perfectly so the resulting code compiles cleanly.
5. OUTPUT FORMAT: Output ONLY the complete updated LaTeX code enclosed inside ```latex ... ``` markdown blocks.
"""

class CVTailor:
    def __init__(self, base_tex_path: str = None):
        if base_tex_path is None:
            base_tex_path = "templates/main.tex" if os.path.exists("templates/main.tex") else "main.tex"
        if not os.path.exists(base_tex_path):
            raise FileNotFoundError(f"Base LaTeX CV file '{base_tex_path}' not found.")
        self.base_tex_path = base_tex_path
        with open(base_tex_path, "r", encoding="utf-8") as f:
            self.base_tex = f.read()
        self.groq_client = GroqClient()

    def tailor_for_job(self, job_title: str, job_description: str, job_id: str = "custom") -> str:
        """Sends the base LaTeX CV and job description to Groq to generate a tailored LaTeX CV."""
        print(f"✨ Tailoring LaTeX CV for job: '{job_title}'...")

        user_prompt = f"""
Base Candidate LaTeX CV (main.tex):
----------------------------------------
{self.base_tex}
----------------------------------------

Target Job Description:
----------------------------------------
Job Title: {job_title}
Job Requirements & Description:
{job_description}
----------------------------------------

Please rewrite the LaTeX CV to optimize ATS compatibility and tailor its content specifically for this job description.
Return ONLY the complete updated LaTeX code inside ```latex ... ``` codeblocks.
"""

        raw_response = self.groq_client.evaluate(
            system_prompt=TAILOR_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model="llama-3.3-70b-versatile"
        )

        # Extract LaTeX code from response
        match = re.search(r"```latex\s*(.*?)\s*```", raw_response, re.DOTALL)
        if match:
            tailored_code = match.group(1).strip()
        else:
            tailored_code = raw_response.strip()

        # Save output to tailored/ folder
        os.makedirs("tailored", exist_ok=True)
        out_filename = f"tailored/tailored_{job_id}.tex"
        with open(out_filename, "w", encoding="utf-8") as f:
            f.write(tailored_code)

        print(f"✅ Tailored LaTeX CV successfully created: {out_filename}")
        return out_filename

def main():
    parser = argparse.ArgumentParser(description="Tailor LaTeX CV for a specific job.")
    parser.add_argument("--job-index", type=int, default=1, help="Index of job in jobs.json (1-indexed)")
    args = parser.parse_args()

    jobs_path = "jobs.json"
    if not os.path.exists(jobs_path):
        print(f"Error: {jobs_path} not found.")
        return

    with open(jobs_path, "r", encoding="utf-8") as f:
        jobs = json.load(f)

    if args.job_index < 1 or args.job_index > len(jobs):
        print(f"Error: Job index {args.job_index} out of range (1 to {len(jobs)}).")
        return

    selected_job = jobs[args.job_index - 1]
    title = selected_job.get("title", "Job Opportunity")
    desc = selected_job.get("description", "")
    job_id = selected_job.get("id", f"job_{args.job_index}")

    tailor = CVTailor("main.tex")
    out_file = tailor.tailor_for_job(job_title=title, job_description=desc, job_id=job_id)
    print(f"\n🎉 Done! Generated tailored CV at: {out_file}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Unified AI-Driven Job Application Automation System
---------------------------------------------------
Integrates:
 1. Job Fetching (LinkedIn / Web Scraper)
 2. AI Fit Evaluation & Match Scoring (Groq LLM)
 3. Resume & Cover Letter Tailoring (LaTeX / DOCX / PDF output)
 4. Google Sheets Tracking (gspread)
 5. Automated Email Dispatch (Google Cloud Console Gmail REST API)
"""

import os
import re
import sys
import json
import time
import datetime
import argparse
from pathlib import Path

# Add src package directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.groq_client import GroqClient
from core.job_fetcher import LinkedInJobFetcher
from core.google_sheets import GoogleSheetManager
from tailoring.pdf_utils import extract_text_from_pdf, load_cv_text
from tailoring.tailor_application import ApplicationTailor
from dispatch.email_dispatcher import GmailAPIDispatcher

EVALUATION_SYSTEM_PROMPT = """You are an expert HR Recruiter and Resume Evaluation Assistant.
Your task is to evaluate how well a candidate's CV matches a specific Job Description.

Evaluation Guidelines:
1. Compare the candidate's skills, experience, projects, and tech stack against the job requirements.
2. Provide a Match Score (%) strictly from 0 to 100 reflecting how well existing qualifications align with the job description.
3. Provide a concise 1-2 sentence explanation of your decision (reasoning).
4. Provide a concise, comma-separated list of the most important technical concepts, tools, frameworks, and behavioral topics likely to be covered in an interview for this role (interview_prep_topics).
5. Estimate the candidate's probability strictly from 0 to 100 (%) of receiving an interview based on the candidate's current CV, tailored CV, and job requirements (acceptance_chance).
6. Clean up and extract the concise Job Title and Company Name for this job listing.

You MUST respond strictly in valid JSON format with the following keys:
{
  "job_title": "<concise job title>",
  "company_name": "<concise company name>",
  "match_score": <integer from 0 to 100>,
  "reasoning": "<short justification>",
  "interview_prep_topics": "<comma-separated list of topics>",
  "acceptance_chance": <integer from 0 to 100>
}
"""


def load_recipient_emails(emails_file: str = None) -> dict:
    """Parses emails.txt into a mapping of company_name (lowercase) -> dict(email, company, person)."""
    if emails_file is None:
        emails_file = "data/emails.txt" if os.path.exists("data/emails.txt") else "emails.txt"

    mapping = {}
    path = Path(emails_file)
    if not path.exists():
        return mapping

    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        email = parts[0]
        company = parts[1] if len(parts) > 1 and parts[1] else None
        person = parts[2] if len(parts) > 2 and parts[2] else "Sir/Mam"

        if company:
            mapping[company.lower()] = {"email": email, "company": company, "person": person}
        
        # Also map by domain core name
        if "@" in email:
            domain_core = email.split("@")[1].split(".")[0].lower()
            if domain_core not in mapping:
                mapping[domain_core] = {"email": email, "company": company or domain_core.capitalize(), "person": person}

    return mapping


def main():
    default_emails = "data/emails.txt" if os.path.exists("data/emails.txt") else "emails.txt"
    default_cv = "data/CV_Fahad.pdf" if os.path.exists("data/CV_Fahad.pdf") else "CV_Fahad.pdf"
    default_jobs = "data/jobs.json" if os.path.exists("data/jobs.json") else "jobs.json"

    parser = argparse.ArgumentParser(
        description="Unified AI Job Evaluation, Resume Tailoring, Google Sheets Sync, and Gmail API Dispatch System."
    )
    parser.add_argument("--fetch", action="store_true", help="Force fetch targeted jobs from config.json")
    parser.add_argument("--all-jobs", action="store_true", help="Generate tailored application files for ALL jobs regardless of score")
    parser.add_argument("--send-emails", action="store_true", help="Automatically dispatch application emails via Google Cloud Gmail API after tailoring")
    parser.add_argument("--send-only", action="store_true", help="ONLY send emails from emails.txt via Google Cloud Gmail API (bypasses job evaluation & tailoring)")
    parser.add_argument("--emails", default=default_emails, help="Path to emails.txt file for email dispatch")
    parser.add_argument("--cv", default=default_cv, help="Path to CV file to attach for email dispatch")
    parser.add_argument("--jobs", default=default_jobs, help="Path to jobs.json file")
    parser.add_argument("--dry-run", action="store_true", help="Run evaluations and previews without sending real emails or writing to production APIs")
    args = parser.parse_args()

    # --- Mode 1: Send Emails Only (Standalone Dispatcher Mode) ---
    if args.send_only:
        print("==========================================================")
        print(" ✉️ STANDALONE GMAIL API EMAIL DISPATCHER MODE")
        print("==========================================================")
        dispatcher = GmailAPIDispatcher()
        dispatcher.dispatch_batch_emails(
            emails_file=args.emails,
            cv_path=args.cv,
            dry_run=args.dry_run
        )
        print("==========================================================")
        print("Done!\n")
        return

    # --- Mode 2: Full Pipeline (Evaluation, Tailoring, Sheets Sync, Optional Auto-Send) ---
    jobs_path = args.jobs
    config_path = "config.json"

    # Load match threshold from config.json
    threshold = 60.0
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                threshold = float(cfg.get("match_threshold", 60.0))
        except Exception as e:
            print(f"⚠️ Could not load threshold from {config_path}: {e}")

    # Step 1: Load & convert PDF CV to text
    pdf_path = args.cv if os.path.exists(args.cv) else default_cv
    print("==========================================================")
    print(" 📄 STEP 1: LOADING CANDIDATE CV")
    print("==========================================================")
    try:
        if os.path.exists(pdf_path):
            cv_text = extract_text_from_pdf(pdf_path)
            cv_source = f"PDF ({pdf_path})"
        else:
            tex_file = "templates/main.tex" if os.path.exists("templates/main.tex") else "main.tex"
            cv_text, cv_source = load_cv_text(tex_path=tex_file, pdf_path=pdf_path)

        print(f"📄 CV Source: {cv_source}")
        print(f"✅ Extracted {len(cv_text)} characters from CV.\n")
    except Exception as e:
        print(f"❌ Failed to extract text from CV: {e}")
        sys.exit(1)

    # Step 2: Fetch jobs if requested or missing
    if args.fetch or not os.path.exists(jobs_path):
        try:
            print("🌐 Fetching jobs from target sources in config.json...")
            fetcher = LinkedInJobFetcher(config_path=config_path, emails_path=args.emails)
            fetcher.fetch_and_save(output_path=jobs_path)
        except Exception as e:
            print(f"⚠️ Could not fetch live jobs ({e}). Proceeding with existing {jobs_path}...\n")

    if not os.path.exists(jobs_path):
        print(f"❌ Error: Jobs JSON file '{jobs_path}' not found!")
        sys.exit(1)

    with open(jobs_path, "r", encoding="utf-8") as f:
        jobs = json.load(f)

    print(f"📋 Loaded {len(jobs)} jobs from '{jobs_path}'. Threshold: {threshold}%\n")

    # Step 3: Initialize services (Groq AI, Application Tailor, Google Sheets, Gmail API)
    try:
        client = GroqClient()
        app_tailor = ApplicationTailor(cv_text=cv_text)
    except Exception as e:
        print(f"❌ Error initializing Groq Client / ApplicationTailor: {e}")
        sys.exit(1)

    gsheet_manager = None
    try:
        gsheet_manager = GoogleSheetManager()
        if not gsheet_manager.client:
            print("⚠️ Google Sheets credentials not configured. Sheet updates will be skipped.\n")
    except Exception as e:
        print(f"⚠️ Google Sheets Manager init warning: {e}\n")

    email_dispatcher = None
    recipient_map = {}
    if args.send_emails:
        try:
            email_dispatcher = GmailAPIDispatcher()
            if not args.dry_run:
                email_dispatcher.initialize_service()
            recipient_map = load_recipient_emails(args.emails)
            print(f"✉️ Gmail API Dispatcher ready. Loaded {len(recipient_map)} company email mapping(s).\n")
        except Exception as e:
            print(f"⚠️ Email Dispatcher init warning: {e}\n")

    # Pipeline Metrics
    total_jobs_processed = 0
    jobs_above_threshold = 0
    tailored_cvs_generated = 0
    gsheet_entries_synced = 0
    emails_dispatched = 0
    failed_jobs = 0

    print("==========================================================")
    print(" 🚀 UNIFIED PIPELINE: EVALUATE, TAILOR, SYNC & DISPATCH")
    print("==========================================================")

    for index, job in enumerate(jobs, start=1):
        total_jobs_processed += 1
        raw_title = job.get("title", "Unknown Title")
        raw_company = job.get("company", "Listing")
        job_desc = job.get("description", "")
        job_url = job.get("url", "")
        direct_email = job.get("contact_email") or job.get("email")

        user_prompt = f"""
Candidate CV:
----------------------------------------
{cv_text}
----------------------------------------

Job Listing Details:
Title: {raw_title}
Company: {raw_company}
URL: {job_url}
Description:
{job_desc}
----------------------------------------
"""

        print(f"\n[{index}/{len(jobs)}] Processing: '{raw_title}' at {raw_company}")

        # AI Fit Evaluation
        try:
            raw_response = client.evaluate(
                system_prompt=EVALUATION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                json_mode=True
            )
            parsed = json.loads(raw_response)

            job_title = parsed.get("job_title") or raw_title
            company_name = parsed.get("company_name") or raw_company
            match_score = float(parsed.get("match_score", 0))
            if match_score <= 10.0 and match_score > 0:
                match_score *= 10.0

            acceptance_chance = float(parsed.get("acceptance_chance", 50))
            if acceptance_chance <= 1.0 and acceptance_chance > 0:
                acceptance_chance *= 100.0

            reasoning = parsed.get("reasoning", "No reasoning provided.")
            interview_prep = parsed.get("interview_prep_topics", "Technical interview, Core skills")
            if isinstance(interview_prep, list):
                interview_prep = ", ".join(interview_prep)

        except Exception as e:
            print(f"   ❌ Failed LLM evaluation for job '{raw_title}': {e}")
            failed_jobs += 1
            continue

        is_above = match_score >= threshold
        if is_above:
            jobs_above_threshold += 1

        processing_status = ""
        generated_out_dir = None

        # Tailor Application Package & Custom Email Message
        if is_above or args.all_jobs:
            try:
                job_for_generator = {
                    "title": job_title,
                    "company": company_name,
                    "description": job_desc,
                    "id": job.get("id", f"JOB-{index}")
                }
                tailor_res = app_tailor.generate_application(job_for_generator)
                tailored_cvs_generated += 1
                
                generated_out_dir = tailor_res.get("output_dir")
                cv_pdf_path = tailor_res.get("cv_pdf_path")
                email_subject = tailor_res.get("email_subject")
                email_body = tailor_res.get("email_body")

                # Store tailored metadata back into the job object
                job["cv_pdf_path"] = cv_pdf_path
                job["email_subject"] = email_subject
                job["email_body"] = email_body
                job["match_score"] = match_score
                job["acceptance_chance"] = acceptance_chance
                job["reasoning"] = reasoning
                job["interview_prep_topics"] = interview_prep
                
                target_contact = direct_email or recipient_map.get(company_name.lower(), {}).get("email")
                if target_contact:
                    job["contact_email"] = target_contact
                    job["job_type"] = "email"
                else:
                    job["job_type"] = "link"

                processing_status = f"Tailored PDF CV created ({cv_pdf_path})"
            except Exception as e:
                print(f"   ❌ Error generating application for '{job_title}': {e}")
                failed_jobs += 1
                processing_status = f"Generation failed ({e})"

            # Sync to Google Sheets
            current_date = datetime.date.today().strftime("%Y-%m-%d")
            try:
                if gsheet_manager:
                    res = gsheet_manager.sync_job(
                        job_title=job_title,
                        company_name=company_name,
                        match_score=match_score,
                        interview_prep_topics=interview_prep,
                        acceptance_chance=acceptance_chance,
                        status="Applied" if job.get("job_type") == "link" else "Ready for Approval",
                        app_date=current_date
                    )
                    gsheet_entries_synced += 1
                    processing_status += f" | Sheet {res.capitalize()}"
            except Exception as e:
                print(f"   ⚠️ Google Sheet sync error: {e}")
        else:
            processing_status = "Skipped (Below Threshold)"

        # Summary output per job
        print(f"   📌 Job Title: {job_title}")
        print(f"   🏢 Company Name: {company_name}")
        print(f"   📊 Match Score: {match_score:.0f}%")
        print(f"   🎯 Acceptance Chance: {acceptance_chance:.0f}%")
        print(f"   💡 Reason: {reasoning}")
        print(f"   ⚙️ Status: {processing_status}")
        time.sleep(1.0)

    # Save updated jobs.json with tailored CV paths & email draft data
    with open(jobs_path, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2)
    print(f"\n💾 Updated '{jobs_path}' with tailored CV paths, match scores, and custom email draft metadata.")

    # Pipeline Summary
    print("\n==========================================================")
    print(" 📊 FINAL PIPELINE SUMMARY")
    print("==========================================================")
    print(f"• Total jobs processed:               {total_jobs_processed}")
    print(f"• Jobs above threshold ({threshold:.0f}%):        {jobs_above_threshold}")
    print(f"• Tailored CVs generated:             {tailored_cvs_generated}")
    print(f"• Google Sheet entries synced:        {gsheet_entries_synced}")
    print(f"• Emails dispatched via Gmail API:    {emails_dispatched}")
    print(f"• Failed jobs:                        {failed_jobs}")
    print("==========================================================")
    print("All tasks completed!\n")


if __name__ == "__main__":
    main()

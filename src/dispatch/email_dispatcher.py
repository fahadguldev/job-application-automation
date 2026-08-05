#!/usr/bin/env python3
"""
Email Dispatcher Module for Job Application Automation
------------------------------------------------------
Uses Google Cloud Console Gmail REST API (OAuth2) to send personalized application
emails with tailored CV attachments.
"""

import os
import re
import sys
import time
import base64
import logging
from pathlib import Path
from email.message import EmailMessage

import socket
socket.setdefaulttimeout(45)

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

SENDER_NAME = os.environ.get("SENDER_NAME", "Muhammad Fahad")
SENDER_EMAIL = os.environ.get("SMTP_USER", "rfgul587@gmail.com")
DELAY_SECONDS = float(os.environ.get("SEND_DELAY_SECONDS", "30"))

GENERIC_DOMAINS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com",
    "aol.com", "protonmail.com", "live.com", "msn.com", "yandex.com",
    "gmx.com", "zoho.com", "mail.com", "rediffmail.com",
}

STRIP_PREFIXES = {"mail", "careers", "career", "jobs", "hr", "recruiting", "www", "talent"}

log_file = "logs/send_log.txt" if os.path.exists("logs") else "send_log.txt"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
)
log = logging.getLogger("EmailDispatcher")


class GmailAPIDispatcher:
    """Manages email dispatching using Google Cloud Console Gmail API (OAuth2)."""

    def __init__(self, credentials_path: str = "credentials.json", token_path: str = "token.json"):
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self.service = None

    def initialize_service(self):
        """Authenticates and initializes the Gmail API service object."""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError:
            log.error(
                "Missing required Google client libraries!\n"
                "Please run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
            )
            raise RuntimeError("Missing Google API libraries")

        creds = None
        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
            except Exception as e:
                log.warning(f"Could not load existing token file ({e}). Will re-authenticate.")

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    log.warning(f"Token refresh failed ({e}). Re-authenticating...")
                    creds = None

            if not creds:
                if not self.credentials_path.exists():
                    log.error(
                        f"Credentials file '{self.credentials_path}' not found!\n"
                        "Please download your OAuth 2.0 Desktop Client JSON file from Google Cloud Console "
                        f"and save it as '{self.credentials_path.name}' in this directory."
                    )
                    raise FileNotFoundError(f"Missing {self.credentials_path}")

                flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), SCOPES)
                creds = flow.run_local_server(port=0)

            # Save credentials for future runs
            self.token_path.write_text(creds.to_json(), encoding="utf-8")
            log.info(f"Saved OAuth token to {self.token_path}")

        self.service = build("gmail", "v1", credentials=creds)
        return self.service

    @staticmethod
    def extract_company(email: str):
        """Guesses company name from domain if available."""
        try:
            domain = email.split("@", 1)[1].lower().strip()
        except IndexError:
            return None

        if domain in GENERIC_DOMAINS:
            return None

        parts = domain.split(".")
        core = parts[0]
        if core in STRIP_PREFIXES and len(parts) > 1:
            core = parts[1]

        words = re.split(r"[-_]", core)
        name = " ".join(w.capitalize() for w in words if w)
        return name or None

    def parse_emails_file(self, emails_path: Path):
        """Parse emails.txt. Each line: email | company | person (pipe-separated)."""
        if not emails_path.exists():
            log.error(f"Emails file not found: {emails_path}")
            return []

        text = emails_path.read_text(encoding="utf-8")
        entries, seen = [], set()
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            email = parts[0]
            company = parts[1] if len(parts) > 1 and parts[1] else self.extract_company(email)
            person = parts[2] if len(parts) > 2 and parts[2] else "Sir/Mam"

            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                log.warning(f"Skipping invalid email: {email!r}")
                continue
            if email.lower() in seen:
                log.warning(f"Skipping duplicate email: {email}")
                continue
            seen.add(email.lower())
            entries.append({"email": email, "company": company, "person": person})
        return entries

    def build_message(
        self,
        recipient: str,
        company: str,
        person: str,
        subject_template: str,
        personalized_template: str,
        generic_template: str,
        cv_path: Path
    ) -> EmailMessage:
        msg = EmailMessage()
        sender = f"{SENDER_NAME} <{SENDER_EMAIL}>" if SENDER_NAME else SENDER_EMAIL
        msg["From"] = sender
        msg["To"] = recipient

        if company:
            body = personalized_template.format(company=company, person=person)
            subject = subject_template.format(company=company) if "{company}" in subject_template else subject_template
        else:
            body = generic_template.format(person=person)
            subject = subject_template.format(company="your company") if "{company}" in subject_template else subject_template

        msg["Subject"] = subject
        msg.set_content(body)

        if cv_path and cv_path.exists():
            cv_bytes = cv_path.read_bytes()
            ext = cv_path.suffix.lower()
            if ext == ".pdf":
                maintype, subtype = "application", "pdf"
            elif ext == ".docx":
                maintype, subtype = "application", "vnd.openxmlformats-officedocument.wordprocessingml.document"
            else:
                maintype, subtype = "application", "octet-stream"
            msg.add_attachment(cv_bytes, maintype=maintype, subtype=subtype, filename=cv_path.name)

        return msg

    def send_single_email(self, email_msg: EmailMessage, dry_run: bool = False, max_retries: int = 3):
        """Sends an EmailMessage using Gmail REST API with automatic retries for network drops/timeouts."""
        if dry_run:
            log.info(f"DRY RUN -> {email_msg['To']} | Subject: {email_msg['Subject']}")
            return True

        if not self.service:
            self.initialize_service()

        raw_message = base64.urlsafe_b64encode(email_msg.as_bytes()).decode("utf-8")
        body = {"raw": raw_message}

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                sent_msg = self.service.users().messages().send(userId="me", body=body).execute(num_retries=3)
                log.info(f"Sent via Gmail API -> {email_msg['To']} (ID: {sent_msg.get('id')})")
                return True
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    wait_sec = attempt * 5
                    log.warning(f"Attempt {attempt}/{max_retries} failed for {email_msg['To']} ({e}). Retrying in {wait_sec}s...")
                    time.sleep(wait_sec)
                    try:
                        self.initialize_service()
                    except Exception:
                        pass
                else:
                    log.error(f"All {max_retries} attempts failed for {email_msg['To']}: {e}")
                    raise last_error

    def dispatch_application(
        self,
        recipient_email: str,
        company_name: str,
        recruiter_name: str = "Hiring Manager",
        cv_path: str = None,
        job_title: str = "Full Stack Developer",
        dry_run: bool = False
    ):
        """Sends a tailored job application email to a specific company/recruiter."""
        if cv_path is None:
            cv_path = "data/CV_Fahad.pdf" if os.path.exists("data/CV_Fahad.pdf") else "CV_Fahad.pdf"

        msg_template_path = Path("templates/message_template.txt") if os.path.exists("templates/message_template.txt") else Path("message_template.txt")
        generic_template_path = Path("templates/generic_message.txt") if os.path.exists("templates/generic_message.txt") else Path("generic_message.txt")

        personalized_template = msg_template_path.read_text(encoding="utf-8") if msg_template_path.exists() else "Dear {person},\n\nI am applying for the software position at {company}.\n\nBest regards,\nMuhammad Fahad"
        generic_template = generic_template_path.read_text(encoding="utf-8") if generic_template_path.exists() else "Dear {person},\n\nI am applying for the software position at your company.\n\nBest regards,\nMuhammad Fahad"

        subject_template = f"Application for {job_title} at {{company}}"
        cv_file = Path(cv_path)

        email_msg = self.build_message(
            recipient=recipient_email,
            company=company_name,
            person=recruiter_name,
            subject_template=subject_template,
            personalized_template=personalized_template,
            generic_template=generic_template,
            cv_path=cv_file
        )

        return self.send_single_email(email_msg, dry_run=dry_run)

    def dispatch_batch_emails(
        self,
        emails_file: str = None,
        cv_path: str = None,
        subject_template: str = "Application for Full Stack Developer at {company}",
        dry_run: bool = False
    ):
        """Dispatches batch emails from emails.txt via Google Cloud Gmail API."""
        if emails_file is None:
            emails_file = "data/emails.txt" if os.path.exists("data/emails.txt") else "emails.txt"
        if cv_path is None:
            cv_path = "data/CV_Fahad.pdf" if os.path.exists("data/CV_Fahad.pdf") else "CV_Fahad.pdf"

        emails_path = Path(emails_file)
        cv_file = Path(cv_path)

        entries = self.parse_emails_file(emails_path)
        if not entries:
            log.error(f"No valid recipient entries found in {emails_path}.")
            return

        msg_template_path = Path("templates/message_template.txt") if os.path.exists("templates/message_template.txt") else Path("message_template.txt")
        generic_template_path = Path("templates/generic_message.txt") if os.path.exists("templates/generic_message.txt") else Path("generic_message.txt")
        personalized_template = msg_template_path.read_text(encoding="utf-8") if msg_template_path.exists() else "Dear {person},\n\nI am applying for the software position at {company}.\n\nBest regards,\nMuhammad Fahad"
        generic_template = generic_template_path.read_text(encoding="utf-8") if generic_template_path.exists() else "Dear {person},\n\nI am applying for the software position at your company.\n\nBest regards,\nMuhammad Fahad"

        if not dry_run and not self.service:
            self.initialize_service()

        log.info(f"Starting batch dispatch via Gmail API to {len(entries)} recipients...")
        sent_count, fail_count = 0, 0

        for i, entry in enumerate(entries, 1):
            email = entry["email"]
            company = entry["company"]
            person = entry["person"]

            email_msg = self.build_message(
                recipient=email,
                company=company,
                person=person,
                subject_template=subject_template,
                personalized_template=personalized_template,
                generic_template=generic_template,
                cv_path=cv_file
            )

            tag = f"[{i}/{len(entries)}]"
            if dry_run:
                log.info(f"{tag} DRY RUN -> {email} | company={company or 'GENERIC'} | person={person}")
                continue

            try:
                self.send_single_email(email_msg, dry_run=False)
                sent_count += 1
            except Exception as e:
                log.error(f"{tag} FAILED -> {email} | {e}")
                fail_count += 1

            if i < len(entries):
                time.sleep(DELAY_SECONDS)

        if dry_run:
            log.info(f"Dry run complete. {len(entries)} email(s) previewed, nothing sent.")
        else:
            log.info(f"Batch dispatch completed. Sent: {sent_count}, Failed: {fail_count}")

    def send_custom_email(
        self,
        recipient_email: str,
        subject: str,
        body_text: str,
        cv_path: str = "CV_Fahad.pdf",
        dry_run: bool = False
    ):
        """Sends a custom email with subject, custom body text, and CV attachment."""
        msg = EmailMessage()
        sender = f"{SENDER_NAME} <{SENDER_EMAIL}>" if SENDER_NAME else SENDER_EMAIL
        msg["From"] = sender
        msg["To"] = recipient_email
        msg["Subject"] = subject
        msg.set_content(body_text)

        cv_file = Path(cv_path)
        if cv_file.exists():
            cv_bytes = cv_file.read_bytes()
            ext = cv_file.suffix.lower()
            if ext == ".pdf":
                maintype, subtype = "application", "pdf"
            elif ext == ".docx":
                maintype, subtype = "application", "vnd.openxmlformats-officedocument.wordprocessingml.document"
            else:
                maintype, subtype = "application", "octet-stream"
            msg.add_attachment(cv_bytes, maintype=maintype, subtype=subtype, filename=cv_file.name)

        return self.send_single_email(msg, dry_run=dry_run)


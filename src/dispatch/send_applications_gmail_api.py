#!/usr/bin/env python3
"""
Email Job Application Automation using Gmail API (Google Cloud Console OAuth2)
-----------------------------------------------------------------------------
Sends a personalized email with your CV attached to a list of recipients using the
official Gmail REST API.

SETUP IN GOOGLE CLOUD CONSOLE:
    1. Go to Google Cloud Console (https://console.cloud.google.com/)
    2. Create a new project (or select an existing one).
    3. Enable the "Gmail API":
       - Go to APIs & Services > Library -> search for "Gmail API" -> click Enable.
    4. Configure OAuth Consent Screen:
       - APIs & Services > OAuth consent screen.
       - User Type: External (or Internal if using Workspace).
       - App info: fill in Name & User Support Email.
       - Developer contact info: your email.
       - Save and continue. Add your email address under "Test users".
    5. Create OAuth 2.0 Client Credentials:
       - APIs & Services > Credentials > Create Credentials > OAuth client ID.
       - Application type: Desktop App.
       - Name: e.g. "Email Application Automation".
       - Click Create, then Download JSON file.
    6. Rename the downloaded file to `credentials.json` and put it in this folder.

INSTALL DEPENDENCIES:
    pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

USAGE:
    # 1. Preview/Dry-run first:
    python send_applications_gmail_api.py --emails emails.txt --cv fahad_cv.pdf --dry-run

    # 2. Authenticate & Send (will open browser window on first run to authorize):
    python send_applications_gmail_api.py --emails emails.txt --cv fahad_cv.pdf
"""

import argparse
import base64
import logging
import os
import re
import sys
import time
from email.message import EmailMessage
from pathlib import Path

import socket
socket.setdefaulttimeout(45)

# Gmail API scopes - gmail.send allows sending emails without reading inbox
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("send_log.txt"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)


def get_gmail_service(credentials_path: Path, token_path: Path):
    """Authenticate and return the Gmail API service object."""
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
        sys.exit(1)

    creds = None
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
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
            if not credentials_path.exists():
                log.error(
                    f"Credentials file '{credentials_path}' not found!\n"
                    "Please download your OAuth 2.0 Desktop Client JSON file from Google Cloud Console "
                    f"and save it as '{credentials_path.name}' in this directory.\n"
                    "See instructions at top of script."
                )
                sys.exit(1)

            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)

        # Save credentials for future runs
        token_path.write_text(creds.to_json(), encoding="utf-8")
        log.info(f"Saved OAuth token to {token_path}")

    return build("gmail", "v1", credentials=creds)


def extract_company(email: str):
    """Guess a company name from an email's domain, or None if it can't."""
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


def load_emails(path: Path):
    """Parse emails.txt. Each line: email | company | person (pipe-separated)."""
    text = path.read_text(encoding="utf-8")
    entries, seen = [], set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        email = parts[0]
        company = parts[1] if len(parts) > 1 and parts[1] else None
        person = parts[2] if len(parts) > 2 and parts[2] else "Sir/Mam"

        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            log.warning(f"Skipping invalid-looking entry: {email!r}")
            continue
        if email.lower() in seen:
            log.warning(f"Skipping duplicate email: {email}")
            continue
        seen.add(email.lower())
        entries.append({"email": email, "company": company, "person": person})
    return entries


def build_message(recipient, company, person, subject_template, personalized_template,
                  generic_template, cv_path: Path):
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


def send_via_gmail_api(service, email_msg: EmailMessage):
    """Encodes an EmailMessage into base64 raw string and posts it to Gmail API."""
    raw_message = base64.urlsafe_b64encode(email_msg.as_bytes()).decode("utf-8")
    body = {"raw": raw_message}
    sent_msg = service.users().messages().send(userId="me", body=body).execute(num_retries=3)
    return sent_msg


def send_all(entries, cv_path, subject_template, personalized_template,
             generic_template, credentials_path: Path, token_path: Path, dry_run=True):
    service = None
    if not dry_run:
        service = get_gmail_service(credentials_path, token_path)

    sent, failed = 0, 0
    for i, entry in enumerate(entries, 1):
        email = entry["email"]
        company = entry["company"]
        person = entry["person"]
        msg = build_message(email, company, person, subject_template, personalized_template,
                            generic_template, cv_path)
        tag = f"[{i}/{len(entries)}]"

        if dry_run:
            log.info(f"{tag} DRY RUN -> {email} | company={company or 'GENERIC'} | person={person} | subject={msg['Subject']!r}")
            continue

        try:
            send_via_gmail_api(service, msg)
            log.info(f"{tag} Sent via Gmail API -> {email} | company={company or 'GENERIC'} | person={person}")
            sent += 1
        except Exception as exc:
            log.error(f"{tag} FAILED via Gmail API -> {email} | {exc}")
            failed += 1

        if i < len(entries):
            time.sleep(DELAY_SECONDS)

    if not dry_run:
        log.info(f"Done. Sent={sent} Failed={failed}")
    else:
        log.info(f"Dry run complete. {len(entries)} email(s) previewed, nothing sent.")


def main():
    parser = argparse.ArgumentParser(description="Send personalized job application emails via Google Cloud Console Gmail API.")
    parser.add_argument("--emails", required=True, help="Path to .txt file with recipient emails")
    parser.add_argument("--cv", required=True, help="Path to your CV file (pdf/docx)")
    parser.add_argument("--credentials", default="credentials.json", help="Path to Google Cloud OAuth credentials JSON")
    parser.add_argument("--token", default="token.json", help="Path to save/load authorized OAuth token")
    parser.add_argument("--subject", default="Application for Full Stack Developer at {company}",
                        help="Subject line template, use {company} as placeholder")
    parser.add_argument("--message", default="message_template.txt",
                        help="Path to .txt file with the personalized message (use {company} and {person})")
    parser.add_argument("--generic-message", default="generic_message.txt",
                        help="Path to .txt file with the generic fallback message (use {person})")
    parser.add_argument("--dry-run", action="store_true", help="Preview everything, send nothing")
    args = parser.parse_args()

    emails_path, cv_path = Path(args.emails), Path(args.cv)
    msg_path, generic_path = Path(args.message), Path(args.generic_message)
    creds_path, token_path = Path(args.credentials), Path(args.token)

    for p in (emails_path, cv_path, msg_path, generic_path):
        if not p.exists():
            log.error(f"File not found: {p}")
            sys.exit(1)

    entries = load_emails(emails_path)
    log.info(f"Loaded {len(entries)} valid recipient(s).")
    if not entries:
        log.error("No valid emails to send to. Exiting.")
        sys.exit(1)

    personalized_template = msg_path.read_text(encoding="utf-8")
    generic_template = generic_path.read_text(encoding="utf-8")

    send_all(entries, cv_path, args.subject, personalized_template, generic_template,
             creds_path, token_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

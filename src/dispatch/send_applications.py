#!/usr/bin/env python3
"""
Email Job Application Automation
---------------------------------
Sends a personalized email with your CV attached to a list of recipients.

USAGE
    # 1. Always dry-run first to sanity-check output before sending anything real
    python send_applications.py --emails emails.txt --cv resume.pdf --dry-run

    # 2. When it looks right, send for real
    python send_applications.py --emails emails.txt --cv resume.pdf

EMAILS.TXT FORMAT
    Each line: email | company_name | person_name
    Example:
        hr@tech-solutions.io | Tech Solutions | Ahmed
        info@startup.com | Startup | Sir/Mam
    - company_name is used in subject and body
    - person_name is used to greet the recipient
    - Lines with just an email (no |) fall back to generic greeting

SETUP
    1. pip install (no extra packages needed - uses only the standard library)
    2. Set SMTP credentials as environment variables before running:
         export SMTP_HOST=smtp.gmail.com
         export SMTP_PORT=587
         export SMTP_USER=you@gmail.com
         export SMTP_PASS=your_app_password   # NOT your normal password
         export SENDER_NAME="Your Name"
    3. For Gmail specifically: turn on 2FA, then create an "App Password" at
       https://myaccount.google.com/apppasswords and use that as SMTP_PASS.

NOTES
    - Respect anti-spam laws (e.g. CAN-SPAM, GDPR) and each company's
      application process where one exists.
    - Rate limiting: there's a delay between sends (default 90s) to reduce the
      chance of your account being throttled or flagged.
    - Gmail/most providers cap you at roughly 400-500 sends/day on a normal
      account - keep lists well under that.
"""

import argparse
import logging
import os
import re
import smtplib
import ssl
import sys
import time
from email.message import EmailMessage
from pathlib import Path

# ---------- Configuration (env vars, with sane defaults) ----------
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "rfgul587@gmail.com")
SMTP_PASS = os.environ.get("SMTP_PASS", "vdev iqgt jfvn bqgy")
SENDER_NAME = os.environ.get("SENDER_NAME", "Muhammad Fahad")

DELAY_SECONDS = float(os.environ.get("SEND_DELAY_SECONDS", "30"))

# Domains that are personal/generic providers - never treated as a "company"
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
    sender = f"{SENDER_NAME} <{SMTP_USER}>" if SENDER_NAME else SMTP_USER
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


def send_all(entries, cv_path, subject_template, personalized_template,
            generic_template, dry_run=True):
    server = None
    if not dry_run:
        if not SMTP_USER or not SMTP_PASS:
            log.error("SMTP_USER / SMTP_PASS are not set. Set them as environment variables. Aborting.")
            sys.exit(1)
        context = ssl.create_default_context()
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls(context=context)
        server.login(SMTP_USER, SMTP_PASS)

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
            server.send_message(msg)
            log.info(f"{tag} Sent -> {email} | company={company or 'GENERIC'} | person={person}")
            sent += 1
        except Exception as exc:
            log.error(f"{tag} FAILED -> {email} | {exc}")
            failed += 1

        if i < len(entries):
            time.sleep(DELAY_SECONDS)

    if server:
        server.quit()
    if not dry_run:
        log.info(f"Done. Sent={sent} Failed={failed}")
    else:
        log.info(f"Dry run complete. {len(entries)} email(s) previewed, nothing sent.")


def main():
    parser = argparse.ArgumentParser(description="Send personalized job application emails with your CV attached.")
    parser.add_argument("--emails", required=True, help="Path to .txt file with recipient emails")
    parser.add_argument("--cv", required=True, help="Path to your CV file (pdf/docx)")
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

    send_all(entries, cv_path, args.subject, personalized_template, generic_template, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
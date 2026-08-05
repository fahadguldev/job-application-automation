# Autonomous Job Application & Outreach AI Agent

An end-to-end autonomous agent system that fetches job postings, evaluates candidate-job fit using Groq LLM, generates tailored resumes and cover letters, syncs job search analytics to Google Sheets, and dispatches personalized emails via the **Google Cloud Console Gmail REST API**.

---

## 🌟 Architecture & Features

1. **Job Scraping & Fetching**: Targets job postings from configured sources in [`config.json`](file:///home/rf-gul/Desktop/New%20Folder/study/self-learning/ai-agents/projects/job-application-automation/config.json).
2. **AI Fit & Match Scoring**: Uses Groq LLM ([`groq_client.py`](file:///home/rf-gul/Desktop/New%20Folder/study/self-learning/ai-agents/projects/job-application-automation/groq_client.py)) to evaluate candidate CV match score (%), interview topics, reasoning, and acceptance probability (%).
3. **Resume & Cover Letter Tailoring**: Rewrites and optimizes candidate resumes and cover letters in PDF / DOCX format tailored specifically to the job description ([`tailor_application.py`](file:///home/rf-gul/Desktop/New%20Folder/study/self-learning/ai-agents/projects/job-application-automation/tailor_application.py)).
4. **Google Sheets Tracking**: Automatically updates a live Google Sheet tracker with application statuses and metrics ([`google_sheets.py`](file:///home/rf-gul/Desktop/New%20Folder/study/self-learning/ai-agents/projects/job-application-automation/google_sheets.py)).
5. **Google Cloud Gmail REST API Dispatcher**: Dispatches personalized job application emails with the newly generated tailored resume attached ([`email_dispatcher.py`](file:///home/rf-gul/Desktop/New%20Folder/study/self-learning/ai-agents/projects/job-application-automation/email_dispatcher.py)).

---

## 🚀 Usage

### 1. Run Pipeline in Preview / Dry-Run Mode
```bash
python main.py --dry-run
```

### 2. Full Execution: Evaluate Jobs, Generate Tailored Resumes & Sync to Google Sheets
```bash
python main.py
```

### 3. Full End-to-End Execution with Gmail REST API Email Dispatch
```bash
python main.py --send-emails
```

### 4. Force Fetch New Jobs & Auto-Dispatch Emails
```bash
python main.py --fetch --send-emails
```

---

## ⚙️ Configuration Files

* [`.env`](file:///home/rf-gul/Desktop/New%20Folder/study/self-learning/ai-agents/projects/job-application-automation/.env): Stores Groq API keys and email environment settings.
* [`credentials.json`](file:///home/rf-gul/Desktop/New%20Folder/study/self-learning/ai-agents/projects/job-application-automation/credentials.json) & [`token.json`](file:///home/rf-gul/Desktop/New%20Folder/study/self-learning/ai-agents/projects/job-application-automation/token.json): Google Cloud OAuth2 credentials for Gmail REST API access.
* [`config.json`](file:///home/rf-gul/Desktop/New%20Folder/study/self-learning/ai-agents/projects/job-application-automation/config.json): Pipeline thresholds and target job configurations.
* [`emails.txt`](file:///home/rf-gul/Desktop/New%20Folder/study/self-learning/ai-agents/projects/job-application-automation/emails.txt): Mapping of target recruiter emails and company names.

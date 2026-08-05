# 🚀 Autonomous AI Job Application & Outreach System

An end-to-end autonomous AI agent pipeline and interactive Web Dashboard designed to fetch targeted job listings, evaluate candidate-job fit using LLMs (Groq / Llama 3.3), generate tailored LaTeX/PDF resumes and custom outreach messages, synchronize analytics to Google Sheets, and dispatch emails via the **Google Cloud Console Gmail REST API**.

---

## 🏗️ Project Architecture & Directory Layout

```
job-application-automation/
├── main.py                     # Main CLI entrypoint script
├── config.json                 # Job search targets, keywords & match threshold
├── pyproject.toml / uv.lock    # Python package dependencies
├── README.md                   # System documentation
├── .env                        # Environment variables & API keys
│
├── src/                        # Core Python Source Package
│   ├── core/                   # Core engines & external APIs
│   │   ├── groq_client.py      # Groq LLM client for job evaluations
│   │   ├── job_fetcher.py      # Tavily / LinkedIn job fetcher & email extractor
│   │   └── google_sheets.py    # Google Sheets tracker manager (gspread)
│   ├── tailoring/              # Resume & Document Tailoring Engine
│   │   ├── tailor_application.py# Application package generator
│   │   ├── tailor_cv.py        # LaTeX CV tailoring engine
│   │   ├── document_generator.py# Tectonic LaTeX PDF & Word DOCX compiler
│   │   └── pdf_utils.py        # PDF text extraction & LaTeX parser
│   └── dispatch/               # Email Dispatch Systems
│       ├── email_dispatcher.py # Gmail REST API dispatcher (OAuth2)
│       ├── send_applications.py# Legacy SMTP email dispatcher
│       └── send_applications_gmail_api.py # Standalone Gmail API runner
│
├── dashboard/                  # Full-Stack Web Application (Express + React Vite)
│   ├── server.js               # Node.js backend server (Port 3001)
│   ├── package.json            # Node.js dependencies & scripts
│   ├── vite.config.js          # Vite frontend configuration
│   └── src/                    # React UI Components & Dashboard layout
│
├── templates/                  # Document & Email Templates
│   ├── main.tex                # Master LaTeX CV template
│   ├── message_template.txt    # Personalized outreach message template
│   └── generic_message.txt    # Fallback outreach message template
│
├── data/                       # Operational Data & Input Files
│   ├── emails.txt              # Recipient email list (`email | company | person`)
│   ├── jobs.json               # Scraped/evaluated jobs database
│   ├── CV_Fahad.pdf            # Primary candidate CV PDF
│   ├── fahad_cv.pdf            # Reference candidate CV PDF
│   └── sent.txt                # Dispatch tracking record
│
├── logs/                       # System & Dispatch Logs
│   └── send_log.txt            # Audit trail log file
│
├── bin/                        # External Binary Utilities
│   └── tectonic                # Bundled Tectonic LaTeX compiler executable
│
└── outputs/                    # Output directory for generated application packages
    └── tailored/               # Output tailored PDF CVs & outreach packages
```

---

## 🛠️ Prerequisites & Dependencies

### 1. System Requirements
- **Python**: 3.10 or higher
- **Node.js**: v18.0 or higher (for Web Dashboard)
- **Tectonic / pdftotext**: Bundled in `bin/tectonic` for exact LaTeX PDF compilation without full TeXLive installation.

### 2. Required API Keys & Environment Variables (`.env`)
Create or configure `.env` in the project root:

```env
# Groq LLM API Key (used for candidate-job match evaluation & resume tailoring)
GROQ_API_KEY=gsk_your_groq_api_key_here

# Tavily Search API Key (used for job scraping & recruiter email discovery)
TAVILY_API_KEY=tvly-your_tavily_api_key_here

# Email Dispatcher Settings
SENDER_NAME="Muhammad Fahad"
SMTP_USER=rfgul587@gmail.com
SEND_DELAY_SECONDS=30
```

### 3. Google Cloud Gmail REST API Credentials
To send emails via official Google Cloud Console Gmail REST API (OAuth2):
1. Enable **Gmail API** in Google Cloud Console.
2. Download your Desktop App OAuth Client JSON and save it as [`credentials.json`](file:///home/rf-gul/Desktop/New%20Folder/study/self-learning/ai-agents/projects/job-application-automation/credentials.json) in the project root directory.
3. On first execution, an OAuth browser window will authorize access and generate [`token.json`](file:///home/rf-gul/Desktop/New%20Folder/study/self-learning/ai-agents/projects/job-application-automation/token.json).

### 4. Input Files & Data Assets
- **Base CV**: Place your base CV as [`data/CV_Fahad.pdf`](file:///home/rf-gul/Desktop/New%20Folder/study/self-learning/ai-agents/projects/job-application-automation/data/CV_Fahad.pdf) or [`templates/main.tex`](file:///home/rf-gul/Desktop/New%20Folder/study/self-learning/ai-agents/projects/job-application-automation/templates/main.tex).
- **Recipient Email List**: Maintain recipient emails in [`data/emails.txt`](file:///home/rf-gul/Desktop/New%20Folder/study/self-learning/ai-agents/projects/job-application-automation/data/emails.txt) using the pipe-separated format:
  ```text
  careers@company.com | Company Name | Contact Person
  ```
- **Job Targets Configuration**: Configure target job titles and search sources in [`config.json`](file:///home/rf-gul/Desktop/New%20Folder/study/self-learning/ai-agents/projects/job-application-automation/config.json).

---

## 💻 Installation & Setup

### Python Backend Environment
```bash
# Activate virtual environment
source venv/bin/python3

# Install dependencies using pyproject.toml / pip
pip install -r requirements.txt  # or: uv sync
```

### Dashboard Web Application Dependencies
```bash
# Navigate to dashboard directory and install Node packages
cd dashboard
npm install
```

---

## 🖥️ Running the Web Dashboard

The project includes a **Web Dashboard UI** built with React, Vite, Tailwind CSS, Express, and Server-Sent Events (SSE) streaming.

### Start Backend & Frontend Concurrently:
```bash
cd dashboard
npm run start
```
- **Backend Express Server**: Runs on `http://localhost:3001`
- **Vite Web Dashboard**: Accessible at `http://localhost:5173`

### Features of the Web Dashboard:
- 📊 **Real-time Pipeline Stream**: Trigger full pipeline runs or send-only dispatch with live SSE console log streaming.
- 📋 **Job Candidates & Match Review**: View job match scores (%), interview preparation topics, reasoning, and tailored application packages.
- ✉️ **Single-Click Email Dispatch**: Review and dispatch custom outreach emails with attachments directly from the browser UI.
- 📝 **Recipient & Config Manager**: Interactively edit `data/emails.txt` and `config.json`.
- 📜 **Log Viewer**: Live monitoring of system logs from `logs/send_log.txt`.

---

## ⚙️ Running via Command Line (CLI)

### 1. Standalone Email Dispatcher Mode (Send Emails Only)
Bypasses job evaluation and dispatches batch emails from `data/emails.txt` using Gmail REST API:
```bash
python main.py --send-only
```

### 2. Dry-Run / Preview Mode
Executes evaluations and previews generated emails/resumes without sending actual emails or modifying Google Sheets:
```bash
python main.py --dry-run
```

### 3. Full Pipeline Execution
Evaluates jobs in `data/jobs.json`, generates tailored CVs in `outputs/tailored/`, and syncs metrics to Google Sheets:
```bash
python main.py
```

### 4. Full Pipeline + Automatic Email Dispatch
```bash
python main.py --send-emails
```

### 5. Fetch New Jobs & Auto-Dispatch Emails
```bash
python main.py --fetch --send-emails
```

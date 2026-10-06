# Job Application Automation

An AI-driven job application pipeline: fetch listings, score fit with an LLM, tailor the resume and cover letter per job, track everything in Google Sheets, and dispatch applications through the Gmail API — all driven from a CLI or a local web dashboard.

- **Live URL:** none published (local CLI + local dashboard on `localhost`)
- **Repository:** https://github.com/fahadguldev/job-application-automation

## Project Overview

`main.py` is an argparse-driven orchestrator over five stages:

```
1. Job fetching      LinkedIn / web scraper     src/core/job_fetcher.py
2. Fit evaluation    Groq LLM match scoring     src/core/groq_client.py
3. Tailoring         resume + cover letter      src/tailoring/*
4. Tracking          Google Sheets (gspread)    src/core/google_sheets.py
5. Dispatch          Gmail REST API             src/dispatch/*
```

A second entry point, `dashboard/`, is a Vite + React + Express app that drives the same pipeline from a browser with live streaming logs.

| Directory | Role |
| --- | --- |
| `main.py` | Unified CLI orchestrator (16 KB, argparse) |
| `src/core/` | `groq_client.py`, `job_fetcher.py` (`LinkedInJobFetcher`), `google_sheets.py` (`GoogleSheetManager`) |
| `src/tailoring/` | `tailor_application.py`, `tailor_cv.py`, `document_generator.py` (20 KB), `pdf_utils.py` |
| `src/dispatch/` | `email_dispatcher.py` (`GmailAPIDispatcher`, 14.9 KB), `send_applications.py`, `send_applications_gmail_api.py` |
| `dashboard/` | React + Express web UI (SSE stream, match review, dispatch, config, logs) |
| `templates/` | Resume / cover-letter templates |
| `data/` | `emails.txt` (recipients), `sent.txt` (dispatch record) |
| `bin/` | Bundled tooling (incl. `tectonic.tar.gz`, a LaTeX engine) |
| `config.json` | Runtime configuration |

## Problem & Solution

Applying to jobs by hand is slow in exactly the wrong places: rewriting the same resume for every posting, keeping a spreadsheet of what was sent, and remembering which version went where.

This system does the repetitive part — it reads a job description, has a model compare it against the CV, emits a per-job tailored resume and cover letter, logs the row to Google Sheets, and sends the application. The human stays in the loop at two points: reviewing match scores in the dashboard, and approving the dispatch.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Language | Python ≥ 3.10, managed with `uv` (`uv.lock`) |
| LLM | `groq` ≥ 0.9.0 — fit scoring, tailoring, interview-topic extraction |
| Web scraping | `requests`, `beautifulsoup4` |
| Google Sheets | `gspread` ≥ 6.0.0 |
| Gmail | `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2` |
| Documents | `python-docx` (DOCX), `pypdf` (PDF text extraction), LaTeX via bundled Tectonic |
| Config | `python-dotenv`, `config.json` |
| Dashboard | Vite + React, Express (`dashboard/server.js`), Recharts, Tailwind, Lucide |
| Dashboard data | Server-Sent Events for live pipeline logs |
| Tooling | `argparse`, `pathlib`, `uv` |

## System Architecture

```
              ┌────────────── CLI ──────────────┐
              │  main.py  (argparse subcommands)│
              └───────────────┬─────────────────┘
                              │
        ┌─────────────────────┼──────────────────────┐
        v                     v                      v
  src/core/             src/tailoring/           src/dispatch/
  job_fetcher.py        tailor_application.py    email_dispatcher.py
    LinkedInJobFetcher  tailor_cv.py               GmailAPIDispatcher
  groq_client.py        document_generator.py     send_applications.py
    (Groq LLM)            DOCX / LaTeX / PDF      send_applications_*.py
  google_sheets.py      pdf_utils.py
    GoogleSheetManager    pypdf extraction
        │                     │                      │
        └──────────┬──────────┴──────────┬───────────┘
                   v                     v
            [ Google Sheets ]     [ Gmail API ]
            one row per job        outreach mail
                   ^                     ^
                   └───── data/sent.txt ─┘  (local dispatch record)

   dashboard/  (parallel entry point)
     App.jsx  ── SSE ──>  server.js  ──>  spawns the same pipeline
     match review, recipient/config editor, log viewer
```

The dashboard does not reimplement the pipeline — it shells out to it and streams stdout back over SSE.

## Key Features

- **Job fetching** — `LinkedInJobFetcher` in `src/core/job_fetcher.py` pulls listings directly or through a scraper path.
- **LLM fit scoring** — `EVALUATION_SYSTEM_PROMPT` in `main.py` forces a strict JSON response with `job_title`, `company_name`, `match_score` (0–100), `reasoning`, `interview_prep_topics`, and `acceptance_chance` (0–100).
- **Resume tailoring** — `tailor_cv.py` rewrites the CV against each job description.
- **Cover letter generation** — `tailor_application.py` produces a per-application letter.
- **Multi-format output** — `document_generator.py` (20 KB) renders DOCX via `python-docx` and PDF via LaTeX; `pdf_utils.py` extracts source text with `pypdf`.
- **Google Sheets tracking** — `GoogleSheetManager` writes one row per job with status and scores.
- **Gmail API dispatch** — `GmailAPIDispatcher` sends through Google's REST API rather than SMTP, with OAuth via `google-auth-oauthlib`.
- **Recipient list** — `data/emails.txt` holds target addresses; editable from the dashboard.
- **Local dispatch log** — `data/sent.txt` records what went out.
- **Web dashboard** — trigger full runs or send-only dispatch with **live SSE console streaming**, view match scores/reasoning/interview topics, dispatch emails with attachments from the browser, edit `data/emails.txt` and `config.json` in place, and tail `logs/send_log.txt`.
- **CLI control** — argparse subcommands in `main.py` for running individual stages or the whole pipeline.

## Setup & Run

```bash
git clone https://github.com/fahadguldev/job-application-automation
cd job-application-automation

uv sync                     # or: pip install -e .
```

Environment (`.env`, gitignored — **never commit values**):

| Variable | Purpose |
| --- | --- |
| Groq API key | LLM fit scoring and tailoring |
| Google OAuth client credentials | Sheets + Gmail access (token stored locally) |
| Scraping/service keys used by `job_fetcher` | job ingestion |

Run the pipeline:

```bash
python main.py --help             # inspect subcommands
python main.py <stage>            # run fetch / evaluate / tailor / track / dispatch
```

Dashboard:

```bash
cd dashboard
npm install
npm run server        # node server.js  (Express + SSE)
npm run dev           # Vite dev server
```

Google Sheets and Gmail both require a one-time OAuth consent flow; the resulting token is cached locally by `google-auth-oauthlib`.

## Technical Decisions

- **Groq instead of a hosted frontier API.** Fast, cheap inference for a high-volume scoring job; the tailoring prompts are structured enough that a smaller model suffices.
- **Strict-JSON prompting.** The evaluation prompt mandates a fixed key set, so downstream code parses instead of guessing — far more robust than free-text and a regex.
- **Sheets as the database.** The target user already lives in a spreadsheet; writing there means no separate admin UI to build or maintain, and the history is shareable.
- **Gmail REST API over SMTP.** OAuth-scoped access, no app-password requirement, and Google-side rate limiting/quotas that behave predictably.
- **Tectonic for LaTeX.** A self-contained TeX engine means `document_generator.py` produces real PDF output without a system TeX installation (~21 MB in `bin/`).
- **`uv` with a committed `uv.lock`.** Reproducible Python dependency resolution, including transitive versions.
- **Dashboard shells out rather than importing.** `server.js` reuses `main.py` exactly as the CLI does, so there is one pipeline implementation and two frontends.
- **SSE over WebSockets for logs.** Log streaming is one-directional; SSE needs no upgrade negotiation and reconnects natively.

## Challenges & Solutions

- **Job postings are inconsistently formatted.** `job_fetcher.py` normalises into a fixed record shape before scoring, so the LLM prompt always sees the same input structure.
- **LLM output breaking the parser.** Solved structurally: the prompt demands JSON with enumerated keys, and the code validates against them rather than tolerating arbitrary prose.
- **Tailored documents must not lose layout.** Templates in `templates/` carry the formatting; the model only fills content slots, keeping `document_generator.py` deterministic.
- **Attachments and threading in outbound mail.** `email_dispatcher.py` (14.9 KB) handles MIME assembly and attachment encoding rather than treating mail as plain text.
- **Re-running must not double-send.** `data/sent.txt` is checked before dispatch to avoid duplicate applications.

## Honest Gaps

- **`emails_dispatched` counter is never incremented.** The dispatch counter stays at `0`, so any reported "sent" total in the dashboard/logs under-reports — the counter is written but not updated on success. Do not trust it as a metric.
- **Committed credentials in the pre-existing README.** The original repository documentation contained plaintext Groq and Tavily API keys. **No values are reproduced here.** Rotate both keys in their provider consoles, and treat any fork/history containing them as compromised.
- **`data/emails.txt` holds real recipient addresses**, and `data/sent.txt` a real dispatch history — personal data committed to a public repository. It should be emptied and gitignored.
- **`bin/tectonic.tar.gz` (~21 MB) is a committed binary** rather than a download step, which inflates the repository substantially.
- **No tests.** There is no unit test for the JSON parsing, sheet writing, or document generation — all three are fragile to prompt/format changes.
- **No `.env.example`.** Required variable names must be read out of `main.py`, `config.json`, and `src/`.
- **Single squashed commit** (2026-08-05), so no development timeline can be inferred.
- **LinkedIn fetching sits in a legal grey area** and has no rate limiting or robots handling in-repo; expect breakage as the site changes markup.

## Deployment Status

| Surface | URL | Status |
| --- | --- | --- |
| CLI | `python main.py` | local |
| Dashboard | `http://localhost` (Vite + Express) | local only |
| Production | — | not deployed |

## Lessons Learned

- Force structured output at the prompt boundary. Every downstream stage becomes a typed parse instead of a string-handling rescue mission.
- When the user already has a system of record, writing into it beats building them a new one — Sheets as the tracker removed an entire admin UI from scope.
- Two frontends over one pipeline is fine; two *implementations* of a pipeline is not. The dashboard shells out to `main.py` for exactly this reason.
- Counters that are never incremented are worse than absent metrics — they look authoritative. Verify a counter moves before displaying it.
- Never commit API keys "just for now" in a README: rotation is the only safe remedy, and history keeps the leak alive after deletion.

## Author

**Muhammad Fahad** - [@fahadguldev](https://github.com/fahadguldev)

Repository: https://github.com/fahadguldev/job-application-automation

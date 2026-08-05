import express from 'express';
import cors from 'cors';
import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3001;
const ROOT_DIR = path.resolve(__dirname, '..');

app.use(cors());
app.use(express.json());
app.use('/outputs', express.static(path.join(ROOT_DIR, 'outputs')));

let activeProcess = null;

// Find Python binary (prefer venv if available)
function getPythonBinary() {
  const venvPy = path.join(ROOT_DIR, 'venv', 'bin', 'python3');
  const dotVenvPy = path.join(ROOT_DIR, '.venv', 'bin', 'python3');
  if (fs.existsSync(venvPy)) return venvPy;
  if (fs.existsSync(dotVenvPy)) return dotVenvPy;
  return 'python3';
}

// Helper: Check if process is truly alive
function isProcessRunning() {
  if (!activeProcess) return false;
  if (activeProcess.exitCode !== null || activeProcess.killed) {
    activeProcess = null;
    return false;
  }
  return true;
}

// Endpoint: Stream script execution output via Server-Sent Events (SSE)
app.post('/api/run', (req, res) => {
  const { force, mode, fetch, sendEmails, sendOnly, dryRun, allJobs } = req.body;

  if (isProcessRunning()) {
    if (force) {
      try {
        activeProcess.kill('SIGKILL');
      } catch (e) {}
      activeProcess = null;
    } else {
      return res.status(400).json({ error: 'A script process is currently running. Click "ABORT" or "Reset Process" to stop it.' });
    }
  }

  const args = ['main.py'];

  if (sendOnly) {
    args.push('--send-only');
  } else {
    if (fetch) args.push('--fetch');
    if (sendEmails) args.push('--send-emails');
    if (allJobs) args.push('--all-jobs');
  }

  if (dryRun) args.push('--dry-run');

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  const pythonBin = getPythonBinary();
  const cmdStr = `${pythonBin} ${args.join(' ')}`;
  
  res.write(`data: ${JSON.stringify({ type: 'start', command: cmdStr })}\n\n`);

  activeProcess = spawn(pythonBin, args, { cwd: ROOT_DIR, env: process.env });

  activeProcess.stdout.on('data', (data) => {
    const lines = data.toString().split('\n');
    lines.forEach((line) => {
      if (line) {
        res.write(`data: ${JSON.stringify({ type: 'stdout', text: line })}\n\n`);
      }
    });
  });

  activeProcess.stderr.on('data', (data) => {
    const lines = data.toString().split('\n');
    lines.forEach((line) => {
      if (line) {
        res.write(`data: ${JSON.stringify({ type: 'stderr', text: line })}\n\n`);
      }
    });
  });

  activeProcess.on('close', (code) => {
    activeProcess = null;
    res.write(`data: ${JSON.stringify({ type: 'end', code })}\n\n`);
    res.end();
  });

  activeProcess.on('error', (err) => {
    activeProcess = null;
    res.write(`data: ${JSON.stringify({ type: 'error', text: err.message })}\n\n`);
    res.end();
  });

  req.on('close', () => {
    // If client disconnects, leave process running or clean up as appropriate
  });
});

// Endpoint: Stop / Reset process
app.post('/api/stop', (req, res) => {
  if (activeProcess) {
    try {
      activeProcess.kill('SIGKILL');
    } catch (e) {}
    activeProcess = null;
    return res.json({ message: 'Execution process stopped and reset.' });
  }
  res.json({ message: 'No process is currently running.' });
});

// Endpoint: Check active status
app.get('/api/status', (req, res) => {
  res.json({ isRunning: isProcessRunning() });
});

// Helper: Resolve data/log paths with fallback
function getFilePath(filename, defaultSubdir = '') {
  if (defaultSubdir) {
    const subPath = path.join(ROOT_DIR, defaultSubdir, filename);
    if (fs.existsSync(subPath)) return subPath;
  }
  const rootPath = path.join(ROOT_DIR, filename);
  if (fs.existsSync(rootPath)) return rootPath;
  return defaultSubdir ? path.join(ROOT_DIR, defaultSubdir, filename) : rootPath;
}

// Endpoint: Get Jobs JSON
app.get('/api/jobs', (req, res) => {
  const filePath = getFilePath('jobs.json', 'data');
  if (fs.existsSync(filePath)) {
    try {
      const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
      return res.json(data);
    } catch (e) {
      return res.status(500).json({ error: 'Could not parse jobs.json' });
    }
  }
  res.json([]);
});

// Endpoint: Update Jobs JSON
app.post('/api/jobs', (req, res) => {
  const filePath = getFilePath('jobs.json', 'data');
  try {
    fs.writeFileSync(filePath, JSON.stringify(req.body, null, 2), 'utf-8');
    res.json({ message: 'Saved jobs.json successfully' });
  } catch (e) {
    res.status(500).json({ error: 'Could not save jobs.json' });
  }
});

// Endpoint: Send Single Approved Job Email
app.post('/api/send-email', (req, res) => {
  const { jobId, recipientEmail, subject, body, cvPath, dryRun } = req.body;
  if (!recipientEmail) {
    return res.status(400).json({ error: 'Recipient email is required' });
  }

  const pythonBin = getPythonBinary();
  
  // Escape strings cleanly for Python inline execution
  const pyCode = `
import sys
from pathlib import Path
sys.path.insert(0, str(Path(${JSON.stringify(ROOT_DIR)}) / "src"))
from dispatch.email_dispatcher import GmailAPIDispatcher

try:
    dispatcher = GmailAPIDispatcher()
    dispatcher.initialize_service()

    res = dispatcher.send_custom_email(
        recipient_email=${JSON.stringify(recipientEmail)},
        subject=${JSON.stringify(subject || 'Job Application')},
        body_text=${JSON.stringify(body || '')},
        cv_path=${JSON.stringify(cvPath || 'data/CV_Fahad.pdf')},
        dry_run=${dryRun ? 'True' : 'False'}
    )
    print("SUCCESS" if res else "FAILED")
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
`;

  const child = spawn(pythonBin, ['-c', pyCode], { cwd: ROOT_DIR, env: process.env });
  let stdoutData = '';
  let stderrData = '';

  child.stdout.on('data', (d) => { stdoutData += d.toString(); });
  child.stderr.on('data', (d) => { stderrData += d.toString(); });

  child.on('close', (code) => {
    if (code === 0 && stdoutData.includes('SUCCESS')) {
      // Mark job as sent in jobs.json
      const jobsPath = getFilePath('jobs.json', 'data');
      if (fs.existsSync(jobsPath)) {
        try {
          const jobsData = JSON.parse(fs.readFileSync(jobsPath, 'utf-8'));
          const target = jobsData.find(j => j.id === jobId);
          if (target) {
            target.email_sent = true;
            target.email_sent_at = new Date().toISOString();
            fs.writeFileSync(jobsPath, JSON.stringify(jobsData, null, 2), 'utf-8');
          }
        } catch (e) {}
      }
      return res.json({ success: true, message: `Email successfully sent to ${recipientEmail}` });
    } else {
      return res.status(500).json({ error: stderrData || stdoutData || 'Failed to dispatch email' });
    }
  });
});

// Endpoint: Get Recipient Emails
app.get('/api/emails', (req, res) => {
  const filePath = getFilePath('emails.txt', 'data');
  if (fs.existsSync(filePath)) {
    const content = fs.readFileSync(filePath, 'utf-8');
    return res.json({ content });
  }
  res.json({ content: '' });
});

// Endpoint: Update Recipient Emails
app.post('/api/emails', (req, res) => {
  const filePath = getFilePath('emails.txt', 'data');
  fs.writeFileSync(filePath, req.body.content || '', 'utf-8');
  res.json({ message: 'Saved emails.txt successfully' });
});

// Endpoint: Get Configuration
app.get('/api/config', (req, res) => {
  const filePath = path.join(ROOT_DIR, 'config.json');
  if (fs.existsSync(filePath)) {
    try {
      const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
      return res.json(data);
    } catch (e) {
      return res.status(500).json({ error: 'Could not parse config.json' });
    }
  }
  res.json({});
});

// Endpoint: Update Configuration
app.post('/api/config', (req, res) => {
  const filePath = path.join(ROOT_DIR, 'config.json');
  fs.writeFileSync(filePath, JSON.stringify(req.body, null, 2), 'utf-8');
  res.json({ message: 'Saved config.json successfully' });
});

// Endpoint: Get Send Log
app.get('/api/logs', (req, res) => {
  const filePath = getFilePath('send_log.txt', 'logs');
  if (fs.existsSync(filePath)) {
    const content = fs.readFileSync(filePath, 'utf-8');
    const lines = content.split('\n').slice(-100).join('\n');
    return res.json({ logs: lines });
  }
  res.json({ logs: '' });
});

app.listen(PORT, () => {
  console.log(`🚀 Job Automation Backend Server running on http://localhost:${PORT}`);
});

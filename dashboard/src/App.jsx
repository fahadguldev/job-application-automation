import React, { useState, useEffect, useRef } from 'react';
import { 
  Zap, 
  Play, 
  Mail, 
  FileText, 
  Globe, 
  Terminal, 
  Settings, 
  Briefcase, 
  Users, 
  Square, 
  CheckCircle2, 
  AlertCircle, 
  Loader2, 
  RefreshCw, 
  Save, 
  Copy, 
  Trash2, 
  ExternalLink,
  ShieldCheck,
  LayoutDashboard,
  Cpu,
  Sparkles,
  Search,
  Check,
  Database,
  Radio,
  TrendingUp,
  RotateCcw
} from 'lucide-react';

const API_BASE = 'http://localhost:3001/api';

export default function App() {
  const [currentView, setCurrentView] = useState('dashboard');
  const [isRunning, setIsRunning] = useState(false);
  const [dryRun, setDryRun] = useState(false);
  const [logs, setLogs] = useState([]);
  const [logFilter, setLogFilter] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  
  const [selectedAction, setSelectedAction] = useState('full');

  const [jobs, setJobs] = useState([]);
  const [jobSearch, setJobSearch] = useState('');
  const [emailsText, setEmailsText] = useState('');
  const [config, setConfig] = useState({ match_threshold: 60, job_titles: [], target_urls: [] });
  const [saveMessage, setSaveMessage] = useState('');
  const [processBlocked, setProcessBlocked] = useState(false);

  const terminalEndRef = useRef(null);

  useEffect(() => {
    fetchJobs();
    fetchEmails();
    fetchConfig();
    checkStatus();
  }, []);

  useEffect(() => {
    if (autoScroll && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const checkStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/status`);
      const data = await res.json();
      setIsRunning(data.isRunning);
    } catch (e) {}
  };

  const fetchJobs = async () => {
    try {
      const res = await fetch(`${API_BASE}/jobs`);
      const data = await res.json();
      if (Array.isArray(data)) setJobs(data);
    } catch (e) {
      console.error('Failed to load jobs', e);
    }
  };

  const fetchEmails = async () => {
    try {
      const res = await fetch(`${API_BASE}/emails`);
      const data = await res.json();
      setEmailsText(data.content || '');
    } catch (e) {
      console.error('Failed to load emails', e);
    }
  };

  const fetchConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/config`);
      const data = await res.json();
      if (data && typeof data === 'object') setConfig(data);
    } catch (e) {
      console.error('Failed to load config', e);
    }
  };

  const saveEmails = async () => {
    try {
      setSaveMessage('Saving emails...');
      await fetch(`${API_BASE}/emails`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: emailsText })
      });
      setSaveMessage('✅ Recipient email directory updated!');
      setTimeout(() => setSaveMessage(''), 3500);
    } catch (e) {
      setSaveMessage('❌ Failed to save emails.');
    }
  };

  const saveConfig = async () => {
    try {
      setSaveMessage('Saving config...');
      await fetch(`${API_BASE}/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      setSaveMessage('✅ Pipeline settings updated!');
      setTimeout(() => setSaveMessage(''), 3500);
    } catch (e) {
      setSaveMessage('❌ Failed to save config.');
    }
  };

  const handleLaunchAgent = (overrideAction = null, forceRun = false) => {
    const actionToRun = overrideAction || selectedAction;
    setIsRunning(true);
    setProcessBlocked(false);
    
    let params = { dryRun, force: forceRun };
    if (actionToRun === 'full') {
      params.title = 'Full Autonomous Pipeline';
      params.fetch = true;
      params.sendEmails = true;
    } else if (actionToRun === 'email_only') {
      params.title = 'Send Emails Only';
      params.sendOnly = true;
    } else if (actionToRun === 'tailor_only') {
      params.title = 'Evaluate & Tailor Resumes';
    } else if (actionToRun === 'fetch_only') {
      params.title = 'Fetch Live Jobs';
      params.fetch = true;
    }

    setLogs((prev) => [
      ...prev,
      { type: 'sys', text: `\n⚡ [${new Date().toLocaleTimeString()}] LAUNCHING AGENT MODE: ${params.title.toUpperCase()}` }
    ]);

    fetch(`${API_BASE}/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params)
    })
      .then(async (response) => {
        if (response.status === 400) {
          const errData = await response.json();
          setIsRunning(false);
          setProcessBlocked(true);
          setLogs((prev) => [
            ...prev,
            { type: 'stderr', text: `⚠️ ${errData.error || 'A script process is already running.'}` }
          ]);
          return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        function read() {
          reader.read().then(({ done, value }) => {
            if (done) {
              setIsRunning(false);
              fetchJobs();
              return;
            }

            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split('\n\n');
            buffer = parts.pop();

            parts.forEach((part) => {
              if (part.startsWith('data: ')) {
                try {
                  const eventData = JSON.parse(part.slice(6));
                  if (eventData.type === 'stdout' || eventData.type === 'stderr') {
                    setLogs((prev) => [...prev, { type: eventData.type, text: eventData.text }]);
                  } else if (eventData.type === 'start') {
                    setLogs((prev) => [...prev, { type: 'sys', text: `▶ Command Executing: ${eventData.command}` }]);
                  } else if (eventData.type === 'end') {
                    setLogs((prev) => [...prev, { type: 'sys', text: `✅ Agent Execution Completed (Code: ${eventData.code})` }]);
                  } else if (eventData.type === 'error') {
                    setLogs((prev) => [...prev, { type: 'stderr', text: `❌ Execution Error: ${eventData.text}` }]);
                  }
                } catch (e) {}
              }
            });

            read();
          });
        }

        read();
      })
      .catch((err) => {
        setIsRunning(false);
        setLogs((prev) => [...prev, { type: 'stderr', text: `❌ Connection Failure: ${err.message}` }]);
      });
  };

  const handleStopAgent = async () => {
    try {
      await fetch(`${API_BASE}/stop`, { method: 'POST' });
      setIsRunning(false);
      setProcessBlocked(false);
      setLogs((prev) => [...prev, { type: 'sys', text: '🛑 Process stop & reset complete.' }]);
    } catch (e) {
      console.error(e);
    }
  };

  const renderLogLine = (logItem, index) => {
    if (logFilter && !logItem.text.toLowerCase().includes(logFilter.toLowerCase())) {
      return null;
    }

    let textStyle = 'text-slate-300';
    if (logItem.type === 'stderr') textStyle = 'text-rose-400 font-semibold';
    else if (logItem.type === 'sys') textStyle = 'text-sky-400 font-bold';
    else if (logItem.text.includes('MATCH') || logItem.text.includes('Match Score:')) textStyle = 'text-emerald-400 font-bold';
    else if (logItem.text.includes('Sent via Gmail API') || logItem.text.includes('Emailed')) textStyle = 'text-purple-400 font-bold';
    else if (logItem.text.includes('FAILED') || logItem.text.includes('Error')) textStyle = 'text-amber-400 font-medium';

    return (
      <div key={index} className={`leading-relaxed flex items-start space-x-3 text-[11px] ${textStyle}`}>
        <span className="text-slate-600 select-none w-8 text-right font-mono opacity-50">{index + 1}</span>
        <span className="flex-1 font-mono">{logItem.text}</span>
      </div>
    );
  };

  const filteredJobs = jobs.filter(j => 
    (j.title || '').toLowerCase().includes(jobSearch.toLowerCase()) ||
    (j.company || '').toLowerCase().includes(jobSearch.toLowerCase())
  );

  const parsedRecruiters = emailsText
    .split('\n')
    .filter(l => l.trim() && !l.startsWith('#'))
    .map(line => {
      const parts = line.split('|').map(p => p.trim());
      return {
        email: parts[0] || '',
        company: parts[1] || 'Direct Contact',
        person: parts[2] || 'Hiring Manager'
      };
    });

  return (
    <div className="flex h-screen overflow-hidden bg-[#070a12] text-slate-100 font-sans">
      
      {/* 1. LEFT SIDEBAR NAVIGATION */}
      <aside className="w-64 glass-sidebar flex flex-col justify-between p-5 hidden md:flex z-20">
        <div className="space-y-6">
          
          <div className="flex items-center space-x-3 px-2 py-1">
            <div className="p-2.5 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 shadow-lg shadow-sky-500/20 text-white">
              <Sparkles className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <h1 className="text-sm font-extrabold tracking-wider text-slate-100 font-heading">ANTIGRAVITY</h1>
              <p className="text-[10px] text-sky-400 font-semibold tracking-widest uppercase">Agent Control OS</p>
            </div>
          </div>

          <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className={`w-2.5 h-2.5 rounded-full ${isRunning ? 'bg-amber-400 animate-ping' : 'bg-emerald-400 pulse-ring'}`} />
              <span className="text-xs font-semibold text-slate-300">
                {isRunning ? 'AGENT BUSY' : 'AGENT READY'}
              </span>
            </div>
            <span className="text-[10px] font-mono text-slate-500">v1.0.0</span>
          </div>

          <nav className="space-y-1">
            <button
              onClick={() => setCurrentView('dashboard')}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-semibold transition ${
                currentView === 'dashboard' 
                  ? 'bg-sky-500/15 text-sky-400 border border-sky-500/30' 
                  : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
              }`}
            >
              <div className="flex items-center space-x-3">
                <LayoutDashboard className="w-4 h-4" />
                <span>Command Center</span>
              </div>
              <span className="w-1.5 h-1.5 rounded-full bg-sky-400" />
            </button>

            <button
              onClick={() => setCurrentView('actions')}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-semibold transition ${
                currentView === 'actions' 
                  ? 'bg-sky-500/15 text-sky-400 border border-sky-500/30' 
                  : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
              }`}
            >
              <div className="flex items-center space-x-3">
                <Zap className="w-4 h-4" />
                <span>Instant Actions</span>
              </div>
            </button>

            <button
              onClick={() => setCurrentView('jobs')}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-semibold transition ${
                currentView === 'jobs' 
                  ? 'bg-sky-500/15 text-sky-400 border border-sky-500/30' 
                  : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
              }`}
            >
              <div className="flex items-center space-x-3">
                <Briefcase className="w-4 h-4" />
                <span>Job Database</span>
              </div>
              <span className="px-1.5 py-0.5 rounded-md bg-slate-800 text-[10px] text-slate-400">{jobs.length}</span>
            </button>

            <button
              onClick={() => setCurrentView('emails')}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-semibold transition ${
                currentView === 'emails' 
                  ? 'bg-sky-500/15 text-sky-400 border border-sky-500/30' 
                  : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
              }`}
            >
              <div className="flex items-center space-x-3">
                <Users className="w-4 h-4" />
                <span>Outreach Directory</span>
              </div>
              <span className="px-1.5 py-0.5 rounded-md bg-slate-800 text-[10px] text-slate-400">{parsedRecruiters.length}</span>
            </button>

            <button
              onClick={() => setCurrentView('settings')}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-semibold transition ${
                currentView === 'settings' 
                  ? 'bg-sky-500/15 text-sky-400 border border-sky-500/30' 
                  : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
              }`}
            >
              <div className="flex items-center space-x-3">
                <Settings className="w-4 h-4" />
                <span>Agent Settings</span>
              </div>
            </button>
          </nav>

        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800/80 space-y-2">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-slate-400 font-medium flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-purple-400" />
              LLM Engine
            </span>
            <span className="text-purple-400 font-semibold font-mono">Groq LLaMA 3.3</span>
          </div>
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-slate-400 font-medium flex items-center gap-1.5">
              <Mail className="w-3.5 h-3.5 text-indigo-400" />
              API Provider
            </span>
            <span className="text-indigo-400 font-semibold font-mono">Gmail REST</span>
          </div>
        </div>
      </aside>

      {/* 2. MAIN CONTENT AREA */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        
        {/* TOP EXECUTIVE APP BAR */}
        <header className="h-16 border-b border-slate-800/80 bg-[#090d16]/90 backdrop-blur-xl px-6 flex items-center justify-between z-10">
          
          <div className="flex items-center space-x-4">
            <h2 className="text-base font-bold text-slate-100 capitalize font-heading flex items-center space-x-2">
              <span>{currentView.replace('_', ' ')}</span>
            </h2>

            <div className="hidden lg:flex items-center space-x-2 text-[11px]">
              <span className="px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-medium flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" />
                Gmail API Active
              </span>
              <span className="px-2.5 py-1 rounded-full bg-sky-500/10 border border-sky-500/20 text-sky-400 font-medium flex items-center gap-1">
                <Database className="w-3 h-3" />
                Google Sheets Linked
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            
            <div className="flex items-center space-x-2 bg-slate-900/80 px-3.5 py-1.5 rounded-xl border border-slate-800">
              <ShieldCheck className={`w-4 h-4 ${dryRun ? 'text-purple-400' : 'text-slate-500'}`} />
              <span className="text-xs font-semibold text-slate-300">Dry Run</span>
              <button 
                onClick={() => setDryRun(!dryRun)}
                className={`w-9 h-5 rounded-full transition-colors relative focus:outline-none ${dryRun ? 'bg-purple-600' : 'bg-slate-700'}`}
              >
                <div className={`w-3.5 h-3.5 rounded-full bg-white absolute top-0.75 transition-transform ${dryRun ? 'translate-x-4.5' : 'translate-x-1'}`} />
              </button>
            </div>

            {(isRunning || processBlocked) && (
              <button
                onClick={handleStopAgent}
                className="px-3 py-1.5 rounded-xl bg-rose-500/20 border border-rose-500/40 text-rose-400 hover:bg-rose-500/30 text-xs font-bold flex items-center space-x-1.5 transition"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>RESET PROCESS</span>
              </button>
            )}

            <button
              onClick={() => { fetchJobs(); fetchEmails(); fetchConfig(); checkStatus(); }}
              className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-xl transition"
              title="Refresh Data"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </header>

        {/* DYNAMIC VIEW BODY */}
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          
          {saveMessage && (
            <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4" />
              <span>{saveMessage}</span>
            </div>
          )}

          {processBlocked && (
            <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-medium flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <AlertCircle className="w-5 h-5 text-amber-400" />
                <span>A script process was active or blocked. Click <strong>RESET & FORCE RUN</strong> to override.</span>
              </div>
              <button
                onClick={() => handleLaunchAgent(null, true)}
                className="px-3.5 py-1.5 rounded-lg bg-amber-500 text-slate-950 font-bold text-xs hover:bg-amber-400 transition"
              >
                RESET & FORCE RUN
              </button>
            </div>
          )}

          {/* VIEW 1: COMMAND CENTER DASHBOARD */}
          {currentView === 'dashboard' && (
            <div className="space-y-6">
              
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                
                <div className="glass-panel glass-panel-hover p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-400">Scraped Listings</span>
                    <div className="p-2 bg-sky-500/10 rounded-lg text-sky-400 border border-sky-500/20">
                      <Briefcase className="w-4 h-4" />
                    </div>
                  </div>
                  <div className="flex items-baseline justify-between">
                    <h3 className="text-2xl font-bold font-heading text-slate-100">{jobs.length}</h3>
                    <span className="text-[11px] font-semibold text-sky-400 bg-sky-500/10 px-2 py-0.5 rounded-full">Jobs Stored</span>
                  </div>
                </div>

                <div className="glass-panel glass-panel-hover p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-400">Match Threshold</span>
                    <div className="p-2 bg-emerald-500/10 rounded-lg text-emerald-400 border border-emerald-500/20">
                      <TrendingUp className="w-4 h-4" />
                    </div>
                  </div>
                  <div className="flex items-baseline justify-between">
                    <h3 className="text-2xl font-bold font-heading text-emerald-400">{config.match_threshold || 60}%</h3>
                    <span className="text-[11px] font-semibold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full">Min Fit Required</span>
                  </div>
                </div>

                <div className="glass-panel glass-panel-hover p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-400">Outreach Contacts</span>
                    <div className="p-2 bg-purple-500/10 rounded-lg text-purple-400 border border-purple-500/20">
                      <Users className="w-4 h-4" />
                    </div>
                  </div>
                  <div className="flex items-baseline justify-between">
                    <h3 className="text-2xl font-bold font-heading text-purple-400">{parsedRecruiters.length}</h3>
                    <span className="text-[11px] font-semibold text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded-full">Recruiters</span>
                  </div>
                </div>

                <div className="glass-panel glass-panel-hover p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-400">Dispatch Protocol</span>
                    <div className="p-2 bg-indigo-500/10 rounded-lg text-indigo-400 border border-indigo-500/20">
                      <Radio className="w-4 h-4" />
                    </div>
                  </div>
                  <div className="flex items-baseline justify-between">
                    <h3 className="text-lg font-bold font-heading text-indigo-400">Gmail OAuth2</h3>
                    <span className="text-[11px] font-semibold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded-full">REST API</span>
                  </div>
                </div>

              </div>

              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                
                <div className="lg:col-span-5 glass-panel p-6 flex flex-col justify-between space-y-6">
                  <div>
                    <div className="flex items-center space-x-2 text-sky-400 text-xs font-bold uppercase tracking-wider mb-1">
                      <Zap className="w-4 h-4" />
                      <span>Agent Launcher</span>
                    </div>
                    <h3 className="text-xl font-bold font-heading text-slate-100">Execute Autonomous Workflow</h3>
                    <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                      Select your desired agent execution mode and launch the pipeline.
                    </p>
                  </div>

                  <div className="space-y-2.5">
                    
                    <div 
                      onClick={() => setSelectedAction('full')}
                      className={`p-3.5 rounded-xl border cursor-pointer transition flex items-center justify-between ${
                        selectedAction === 'full' 
                          ? 'bg-sky-500/15 border-sky-500/50 glow-border-sky' 
                          : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center space-x-3">
                        <div className="p-2 rounded-lg bg-sky-500/20 text-sky-400">
                          <Sparkles className="w-4 h-4" />
                        </div>
                        <div>
                          <h4 className="text-xs font-bold text-slate-100">Full Pipeline Agent</h4>
                          <p className="text-[11px] text-slate-400">Fetch jobs $\rightarrow$ AI evaluation $\rightarrow$ Tailor CV $\rightarrow$ Gmail API Send</p>
                        </div>
                      </div>
                      {selectedAction === 'full' && <Check className="w-4 h-4 text-sky-400" />}
                    </div>

                    <div 
                      onClick={() => setSelectedAction('email_only')}
                      className={`p-3.5 rounded-xl border cursor-pointer transition flex items-center justify-between ${
                        selectedAction === 'email_only' 
                          ? 'bg-purple-500/15 border-purple-500/50 glow-border-purple' 
                          : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center space-x-3">
                        <div className="p-2 rounded-lg bg-purple-500/20 text-purple-400">
                          <Mail className="w-4 h-4" />
                        </div>
                        <div>
                          <h4 className="text-xs font-bold text-slate-100">Send Emails Only</h4>
                          <p className="text-[11px] text-slate-400">Batch dispatch outreach emails from emails.txt</p>
                        </div>
                      </div>
                      {selectedAction === 'email_only' && <Check className="w-4 h-4 text-purple-400" />}
                    </div>

                    <div 
                      onClick={() => setSelectedAction('tailor_only')}
                      className={`p-3.5 rounded-xl border cursor-pointer transition flex items-center justify-between ${
                        selectedAction === 'tailor_only' 
                          ? 'bg-emerald-500/15 border-emerald-500/50 glow-border-emerald' 
                          : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center space-x-3">
                        <div className="p-2 rounded-lg bg-emerald-500/20 text-emerald-400">
                          <FileText className="w-4 h-4" />
                        </div>
                        <div>
                          <h4 className="text-xs font-bold text-slate-100">Evaluate & Tailor Only</h4>
                          <p className="text-[11px] text-slate-400">AI fit evaluation & tailored resume PDF creation</p>
                        </div>
                      </div>
                      {selectedAction === 'tailor_only' && <Check className="w-4 h-4 text-emerald-400" />}
                    </div>

                    <div 
                      onClick={() => setSelectedAction('fetch_only')}
                      className={`p-3.5 rounded-xl border cursor-pointer transition flex items-center justify-between ${
                        selectedAction === 'fetch_only' 
                          ? 'bg-indigo-500/15 border-indigo-500/50' 
                          : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center space-x-3">
                        <div className="p-2 rounded-lg bg-indigo-500/20 text-indigo-400">
                          <Globe className="w-4 h-4" />
                        </div>
                        <div>
                          <h4 className="text-xs font-bold text-slate-100">Fetch Jobs Only</h4>
                          <p className="text-[11px] text-slate-400">Scrape target LinkedIn company pages</p>
                        </div>
                      </div>
                      {selectedAction === 'fetch_only' && <Check className="w-4 h-4 text-indigo-400" />}
                    </div>

                  </div>

                  <button
                    onClick={() => handleLaunchAgent()}
                    disabled={isRunning}
                    className="w-full py-3.5 px-6 rounded-xl bg-gradient-to-r from-sky-500 via-indigo-600 to-purple-600 hover:from-sky-400 hover:to-purple-500 text-white font-bold text-xs tracking-wider uppercase shadow-xl shadow-sky-500/20 flex items-center justify-center space-x-2 transition disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isRunning ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin text-white" />
                        <span>AGENT RUNNING...</span>
                      </>
                    ) : (
                      <>
                        <Play className="w-4 h-4 fill-current" />
                        <span>LAUNCH AGENT NOW</span>
                      </>
                    )}
                  </button>

                </div>

                <div className="lg:col-span-7 glass-panel flex flex-col overflow-hidden h-[520px]">
                  
                  <div className="bg-slate-900/90 border-b border-slate-800 px-4 py-3 flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 rounded-full bg-rose-500/80" />
                      <div className="w-3 h-3 rounded-full bg-amber-500/80" />
                      <div className="w-3 h-3 rounded-full bg-emerald-500/80" />
                      <span className="ml-2 text-xs font-mono text-slate-400">live_agent_output.log</span>
                    </div>

                    <div className="flex items-center space-x-2">
                      <input
                        type="text"
                        placeholder="Filter logs..."
                        value={logFilter}
                        onChange={(e) => setLogFilter(e.target.value)}
                        className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-300 focus:outline-none focus:border-sky-500 w-32"
                      />
                      
                      <button
                        onClick={() => setLogs([])}
                        className="p-1 text-slate-400 hover:text-slate-200 transition"
                        title="Clear Console"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>

                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(logs.map(l => l.text).join('\n'));
                          alert('Logs copied to clipboard!');
                        }}
                        className="p-1 text-slate-400 hover:text-slate-200 transition"
                        title="Copy Logs"
                      >
                        <Copy className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  <div className="flex-1 p-4 bg-slate-950/90 overflow-y-auto space-y-1">
                    {logs.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center text-slate-600 space-y-2">
                        <Terminal className="w-8 h-8 opacity-40" />
                        <p className="text-xs font-mono">Terminal ready. Click 'LAUNCH AGENT NOW' to begin execution.</p>
                      </div>
                    ) : (
                      logs.map((item, idx) => renderLogLine(item, idx))
                    )}
                    <div ref={terminalEndRef} />
                  </div>

                </div>

              </div>

              <div className="glass-panel p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-base font-bold font-heading text-slate-100">Stored Job Candidates</h3>
                    <p className="text-xs text-slate-400">Listings parsed and evaluated from jobs.json</p>
                  </div>
                  
                  <div className="flex items-center space-x-3">
                    <div className="relative">
                      <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-500" />
                      <input
                        type="text"
                        placeholder="Search jobs..."
                        value={jobSearch}
                        onChange={(e) => setJobSearch(e.target.value)}
                        className="pl-9 pr-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-sky-500 w-48"
                      />
                    </div>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-400 uppercase tracking-wider text-[10px]">
                        <th className="py-3 px-4">Job Title</th>
                        <th className="py-3 px-4">Company</th>
                        <th className="py-3 px-4">Match Status</th>
                        <th className="py-3 px-4 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {filteredJobs.slice(0, 8).map((j, i) => (
                        <tr key={i} className="hover:bg-slate-900/40 transition">
                          <td className="py-3 px-4 font-semibold text-slate-200">{j.title || 'Software Role'}</td>
                          <td className="py-3 px-4 text-sky-400 font-medium">{j.company || 'Company'}</td>
                          <td className="py-3 px-4">
                            <span className="px-2.5 py-1 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                              Parsed Candidate
                            </span>
                          </td>
                          <td className="py-3 px-4 text-right">
                            {j.url && (
                              <a
                                href={j.url}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center space-x-1 text-slate-400 hover:text-sky-400 transition"
                              >
                                <span>Link</span>
                                <ExternalLink className="w-3 h-3" />
                              </a>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

              </div>

            </div>
          )}

          {/* VIEW 2: INSTANT ACTIONS */}
          {currentView === 'actions' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              
              <div className="glass-panel p-6 space-y-4 border-l-4 border-l-sky-500">
                <div className="flex items-center space-x-3 text-sky-400">
                  <Zap className="w-6 h-6" />
                  <h3 className="text-lg font-bold font-heading text-slate-100">Full Autonomous Pipeline</h3>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Performs complete end-to-end execution: Scrapes LinkedIn target pages, evaluates candidate fit using Groq LLM, generates tailored resume PDF & cover letter, updates Google Sheets, and dispatches personalized emails via Google Cloud Gmail REST API.
                </p>
                <button
                  onClick={() => handleLaunchAgent('full')}
                  disabled={isRunning}
                  className="px-5 py-2.5 rounded-xl bg-sky-500 hover:bg-sky-400 text-white font-bold text-xs flex items-center space-x-2 transition"
                >
                  <Play className="w-4 h-4 fill-current" />
                  <span>Execute Full Pipeline</span>
                </button>
              </div>

              <div className="glass-panel p-6 space-y-4 border-l-4 border-l-purple-500">
                <div className="flex items-center space-x-3 text-purple-400">
                  <Mail className="w-6 h-6" />
                  <h3 className="text-lg font-bold font-heading text-slate-100">Send Emails Only</h3>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Bypasses job fetching and AI evaluation. Directly parses recipient list from emails.txt and sends outreach emails with candidate CV attached via Google Cloud Console Gmail REST API.
                </p>
                <button
                  onClick={() => handleLaunchAgent('email_only')}
                  disabled={isRunning}
                  className="px-5 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs flex items-center space-x-2 transition"
                >
                  <Mail className="w-4 h-4" />
                  <span>Dispatch Outreach Emails</span>
                </button>
              </div>

              <div className="glass-panel p-6 space-y-4 border-l-4 border-l-emerald-500">
                <div className="flex items-center space-x-3 text-emerald-400">
                  <FileText className="w-6 h-6" />
                  <h3 className="text-lg font-bold font-heading text-slate-100">Evaluate & Tailor Only</h3>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Runs AI candidate fit evaluation against jobs.json, generates tailored resume DOCX/PDF packages, and logs application scores to Google Sheets without sending emails.
                </p>
                <button
                  onClick={() => handleLaunchAgent('tailor_only')}
                  disabled={isRunning}
                  className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center space-x-2 transition"
                >
                  <FileText className="w-4 h-4" />
                  <span>Run Resume Tailor</span>
                </button>
              </div>

              <div className="glass-panel p-6 space-y-4 border-l-4 border-l-indigo-500">
                <div className="flex items-center space-x-3 text-indigo-400">
                  <Globe className="w-6 h-6" />
                  <h3 className="text-lg font-bold font-heading text-slate-100">Fetch Live Jobs</h3>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Connects to target URLs in config.json and fetches the latest software engineering job listings into jobs.json.
                </p>
                <button
                  onClick={() => handleLaunchAgent('fetch_only')}
                  disabled={isRunning}
                  className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs flex items-center space-x-2 transition"
                >
                  <Globe className="w-4 h-4" />
                  <span>Scrape New Listings</span>
                </button>
              </div>

            </div>
          )}

          {/* VIEW 3: JOB DATABASE */}
          {currentView === 'jobs' && (
            <div className="glass-panel p-6 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-bold font-heading text-slate-100">Scraped Jobs Database ({jobs.length})</h3>
                  <p className="text-xs text-slate-400">View and manage parsed job listings</p>
                </div>
                <button
                  onClick={fetchJobs}
                  className="px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-sky-400 flex items-center space-x-1.5 transition"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Reload Database</span>
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {jobs.map((j, i) => (
                  <div key={i} className="p-4 rounded-xl bg-slate-900/80 border border-slate-800/80 flex flex-col justify-between space-y-3">
                    <div>
                      <div className="flex items-start justify-between">
                        <h4 className="font-bold text-slate-200 text-xs">{j.title || 'Software Engineer'}</h4>
                        {j.url && (
                          <a href={j.url} target="_blank" rel="noreferrer" className="text-slate-500 hover:text-sky-400">
                            <ExternalLink className="w-3.5 h-3.5" />
                          </a>
                        )}
                      </div>
                      <p className="text-[11px] font-semibold text-sky-400 mt-0.5">{j.company || 'Company'}</p>
                      {j.description && (
                        <p className="text-[11px] text-slate-400 mt-2 line-clamp-3 leading-relaxed">{j.description}</p>
                      )}
                    </div>

                    <div className="pt-2 border-t border-slate-800/60 flex items-center justify-between text-[10px] text-slate-500 font-mono">
                      <span>ID: {j.id || `JOB-${i+1}`}</span>
                      <span className="text-emerald-400">Ready for evaluation</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* VIEW 4: OUTREACH DIRECTORY */}
          {currentView === 'emails' && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              
              <div className="lg:col-span-5 glass-panel p-6 space-y-4">
                <h3 className="text-base font-bold font-heading text-slate-100">Parsed Recruiter Directory ({parsedRecruiters.length})</h3>
                <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
                  {parsedRecruiters.map((r, i) => (
                    <div key={i} className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-bold text-slate-200">{r.person}</h4>
                        <span className="text-[10px] font-semibold text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded-full">{r.company}</span>
                      </div>
                      <p className="text-[11px] font-mono text-sky-400">{r.email}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="lg:col-span-7 glass-panel p-6 space-y-4 flex flex-col">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-base font-bold font-heading text-slate-100">Raw emails.txt Editor</h3>
                    <p className="text-xs text-slate-400">Format: email | company_name | recruiter_name</p>
                  </div>
                  <button
                    onClick={saveEmails}
                    className="px-4 py-2 rounded-xl bg-sky-500 hover:bg-sky-400 text-white font-bold text-xs flex items-center space-x-2 transition"
                  >
                    <Save className="w-4 h-4" />
                    <span>Save Emails</span>
                  </button>
                </div>

                <textarea
                  value={emailsText}
                  onChange={(e) => setEmailsText(e.target.value)}
                  rows={14}
                  className="flex-1 w-full p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200 focus:outline-none focus:border-sky-500"
                />
              </div>

            </div>
          )}

          {/* VIEW 5: AGENT SETTINGS */}
          {currentView === 'settings' && (
            <div className="glass-panel p-6 space-y-6 max-w-3xl">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-bold font-heading text-slate-100">Pipeline & Scraper Configuration</h3>
                  <p className="text-xs text-slate-400">Manage match score thresholds and scraping parameters in config.json</p>
                </div>
                <button
                  onClick={saveConfig}
                  className="px-4 py-2 rounded-xl bg-sky-500 hover:bg-sky-400 text-white font-bold text-xs flex items-center space-x-2 transition"
                >
                  <Save className="w-4 h-4" />
                  <span>Save Configuration</span>
                </button>
              </div>

              <div className="space-y-5">
                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-2">
                    Minimum Fit Match Threshold: <span className="text-sky-400 font-bold">{config.match_threshold || 60}%</span>
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={config.match_threshold || 60}
                    onChange={(e) => setConfig({ ...config, match_threshold: parseInt(e.target.value) })}
                    className="w-full accent-sky-400 cursor-pointer"
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Target Job Titles (comma separated)</label>
                  <input
                    type="text"
                    value={Array.isArray(config.job_titles) ? config.job_titles.join(', ') : ''}
                    onChange={(e) => setConfig({ ...config, job_titles: e.target.value.split(',').map(s => s.trim()) })}
                    className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Target LinkedIn Company URLs (comma separated)</label>
                  <input
                    type="text"
                    value={Array.isArray(config.target_urls) ? config.target_urls.join(', ') : ''}
                    onChange={(e) => setConfig({ ...config, target_urls: e.target.value.split(',').map(s => s.trim()) })}
                    className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                  />
                </div>
              </div>
            </div>
          )}

        </main>
      </div>

    </div>
  );
}

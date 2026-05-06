"use client";

import {
  ArrowUpRight,
  Heart,
  X,
  Check,
  Filter,
  Play,
  Loader2,
  Activity,
  Briefcase,
  ChevronRight,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

// ── JobCard ───────────────────────────────────────────────────
function JobCard({ job }: { job: any }) {
  const isTopMatch = job.match >= 90;
  return (
    <div className="orion-card p-5 relative overflow-hidden group hover:border-[#C1F034]/30 transition-colors flex flex-col h-full">
      <div className="flex justify-between items-start mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-white flex items-center justify-center text-black font-bold text-xl uppercase">
            {job.initial}
          </div>
          <div>
            <h3 className="font-semibold text-white">{job.title}</h3>
            <p className="text-xs text-white/50">{job.company} • {job.time}</p>
          </div>
        </div>
        {job.apply_url && (
          <a href={job.apply_url} target="_blank" rel="noopener noreferrer"
            className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center border border-white/10 hover:bg-white/10">
            <ArrowUpRight className="w-3 h-3 text-white/60" />
          </a>
        )}
      </div>

      <div className="flex flex-wrap gap-2 mb-8">
        {job.salary && <span className="px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-[10px] font-medium text-white/80">{job.salary}</span>}
        {job.status && <span className="px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-[10px] font-medium text-white/80">{job.status}</span>}
        {job.location && <span className="px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-[10px] font-medium text-white/80">{job.location}</span>}
        {job.source && <span className="px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-[10px] font-medium text-white/80">{job.source}</span>}
      </div>

      <div className="flex items-end justify-between mt-auto">
        {job.matched_skills && job.matched_skills.length > 0 && (
          <div className="flex flex-wrap gap-1 max-w-[60%]">
            {job.matched_skills.slice(0, 3).map((s: string, i: number) => (
              <span key={i} className="text-[9px] px-2 py-0.5 rounded-full bg-[#C1F034]/10 text-[#C1F034] border border-[#C1F034]/20">{s}</span>
            ))}
          </div>
        )}

        <div className="relative w-20 h-20 flex items-center justify-center shrink-0">
          <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="40" fill="transparent" stroke="rgba(255,255,255,0.1)" strokeWidth="6" />
            <circle cx="50" cy="50" r="40" fill="transparent" stroke="#C1F034" strokeWidth="6" strokeDasharray="251.2" strokeDashoffset={251.2 * (1 - job.match / 100)} strokeLinecap="round" />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-xl font-bold text-white leading-none">{job.match}%</span>
            <span className="text-[8px] text-[#C1F034] uppercase font-bold mt-0.5">{isTopMatch ? "Top Match" : "Match"}</span>
          </div>
          {job.match >= 85 && (
            <div className="absolute -left-4 top-2 w-6 h-6 rounded-full bg-[#C1F034] flex items-center justify-center border-2 border-[#121214]">
              <Heart className="w-3 h-3 text-black fill-black" />
            </div>
          )}
          <div className="absolute left-0 bottom-0 w-5 h-5 rounded-full bg-white/10 backdrop-blur-md flex items-center justify-center border border-white/20">
            <Check className="w-2.5 h-2.5 text-white" />
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────
export default function DashboardPage() {
  const [isScanning, setIsScanning] = useState(false);
  const [scanStep, setScanStep] = useState(0);
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    total_applied: 0,
    applied_today: 0,
    applied_this_week: 0,
    interviews: 0,
    rejections: 0,
    response_rate: 0,
  });

  const scanSteps = [
    "Parsing resume...",
    "Scraping jobs...",
    "Filtering...",
    "Scoring matches...",
    "Auto applying...",
    "Done",
  ];

  // ── Load real data on mount ──
  const loadApplications = useCallback(async () => {
    try {
      const data = await api.getApplications();
      if (data && Array.isArray(data.applications) && data.applications.length > 0) {
        const mapped = data.applications.map((app: any) => ({
          title: app.job?.title || "Unknown Role",
          company: app.job?.company || "Unknown",
          time: app.applied_at ? new Date(app.applied_at).toLocaleDateString() : "—",
          salary: app.job?.salary_range || null,
          status: app.status,
          location: app.job?.location || null,
          source: app.job?.source || null,
          apply_url: app.job?.apply_url || null,
          match: app.match_score || 0,
          matched_skills: app.matched_skills || [],
          missing_skills: app.missing_skills || [],
          initial: (app.job?.company || "?")[0].toUpperCase(),
        }));
        setJobs(mapped);
      }
    } catch {
      // No data yet — show empty state
    } finally {
      setLoading(false);
    }
  }, []);

  const loadStats = useCallback(async () => {
    try {
      const data = await api.getStats();
      if (data) {
        setStats({
          total_applied: data.total_applied ?? 0,
          applied_today: data.applied_today ?? 0,
          applied_this_week: data.applied_this_week ?? 0,
          interviews: data.interviews ?? 0,
          rejections: data.rejections ?? 0,
          response_rate: data.response_rate_percent ?? 0,
        });
      }
    } catch {
      // Keep defaults
    }
  }, []);

  useEffect(() => {
    loadApplications();
    loadStats();
  }, [loadApplications, loadStats]);

  // ── Start scan ──
  const startScan = async () => {
    setIsScanning(true);
    setScanStep(0);

    try {
      const { scan_id } = await api.runScan();

      // Animate through steps while waiting
      const stepInterval = setInterval(() => {
        setScanStep(prev => (prev < scanSteps.length - 2 ? prev + 1 : prev));
      }, 6000);

      // Poll status
      const pollInterval = setInterval(async () => {
        try {
          const status = await api.getScanStatus(scan_id);

          if (status.status === "completed") {
            clearInterval(pollInterval);
            clearInterval(stepInterval);
            setScanStep(scanSteps.length - 1);
            setTimeout(() => {
              setIsScanning(false);
              loadApplications();
              loadStats();
            }, 2000);
          }

          if (status.status === "failed") {
            clearInterval(pollInterval);
            clearInterval(stepInterval);
            setIsScanning(false);
          }
        } catch {
          // ignore poll errors
        }
      }, 3000);

    } catch {
      setIsScanning(false);
    }
  };

  return (
    <div className="w-full max-w-[1600px] mx-auto animate-in fade-in duration-700 font-sans mt-2 pb-20 text-white">

      {/* ═══ HERO SECTION ═══ */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 relative min-h-[480px]">

        {/* Left: Title + Stats */}
        <div className="lg:col-span-5 flex flex-col justify-between pt-8 z-10 relative">
          <div>
            <h1 className="text-5xl lg:text-6xl font-light tracking-tight leading-tight mb-2 uppercase">
              YOUR <br />
              <span className="font-bold">JOB MATCH</span>
            </h1>
            <div className="flex items-center gap-2 mb-8">
              <span className="px-2 py-0.5 rounded bg-white/10 text-[10px] font-bold text-white uppercase tracking-wider border border-white/20">AI-Powered</span>
            </div>
          </div>

          <div className="orion-card p-6 w-[85%] mt-auto">
            <div className="flex justify-between items-start mb-6">
              <h3 className="text-sm font-medium text-white/80">Pipeline Summary</h3>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <div className="text-2xl font-bold stat-number">{stats.total_applied}</div>
                <div className="text-[10px] text-white/50 uppercase mt-1">Total Applied</div>
              </div>
              <div>
                <div className="text-2xl font-bold stat-number">{stats.applied_this_week}</div>
                <div className="text-[10px] text-white/50 uppercase mt-1">This Week</div>
              </div>
              <div>
                <div className="text-2xl font-bold stat-number text-[#C1F034]">{stats.interviews}</div>
                <div className="text-[10px] text-white/50 uppercase mt-1">Interviews</div>
              </div>
            </div>
          </div>
        </div>

        {/* Center/Right */}
        <div className="lg:col-span-7 relative flex justify-center items-center">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-[#C1F034]/10 blur-[100px] rounded-full pointer-events-none" />

          {/* Scan card */}
          <div className="relative z-10 w-full max-w-md orion-card p-8 border border-[#C1F034]/20 glow-neon">
            <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
              <Activity className="w-5 h-5 text-[#C1F034]" />
              Agent Operations
            </h2>

            <AnimatePresence mode="wait">
              {!isScanning ? (
                <motion.div
                  key="idle"
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                  className="flex flex-col items-center justify-center py-8"
                >
                  <button
                    onClick={startScan}
                    className="w-24 h-24 rounded-full bg-[#C1F034] text-black flex items-center justify-center hover:scale-105 transition-transform shadow-[0_0_30px_rgba(193,240,52,0.4)]"
                  >
                    <Play className="w-8 h-8 ml-1" />
                  </button>
                  <p className="mt-6 font-medium text-white/80">Start new scan</p>
                  <p className="text-xs text-white/50 mt-2 text-center max-w-[200px]">Agent will search, filter, and auto-apply based on your settings.</p>
                </motion.div>
              ) : (
                <motion.div
                  key="scanning"
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                  className="py-4"
                >
                  <div className="space-y-4">
                    {scanSteps.map((step, idx) => {
                      const isActive = idx === scanStep;
                      const isPast = idx < scanStep;
                      return (
                        <div key={step} className="flex items-center gap-4">
                          <div className={`w-8 h-8 rounded-full flex items-center justify-center border transition-colors ${isPast ? "bg-[#C1F034] border-[#C1F034] text-black" :
                              isActive ? "bg-white/10 border-[#C1F034] text-[#C1F034]" :
                                "bg-transparent border-white/20 text-white/30"
                            }`}>
                            {isPast ? <Check className="w-4 h-4" /> :
                              isActive ? <Loader2 className="w-4 h-4 animate-spin" /> :
                                <div className="w-1.5 h-1.5 rounded-full bg-current" />}
                          </div>
                          <span className={`text-sm font-medium transition-colors ${isPast ? "text-white" :
                              isActive ? "text-[#C1F034]" :
                                "text-white/30"
                            }`}>
                            {step}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Right metrics column */}
          <div className="absolute right-0 top-0 bottom-0 flex flex-col justify-between py-6 w-[320px] pointer-events-none z-20">

            {/* Daily Metrics */}
            <div className="orion-card p-5 pointer-events-auto">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-sm font-medium">Daily Metrics</h3>
              </div>
              <div className="flex items-end gap-6 mb-4">
                <div>
                  <div className="text-2xl font-bold stat-number">{stats.applied_today}</div>
                  <div className="text-[10px] text-white/50 uppercase mt-1">Today</div>
                </div>
                <div>
                  <div className="text-2xl font-bold stat-number">{stats.applied_this_week}</div>
                  <div className="text-[10px] text-white/50 uppercase mt-1">This Week</div>
                </div>
                <div>
                  <div className="text-2xl font-bold stat-number">{stats.interviews}</div>
                  <div className="text-[10px] text-white/50 uppercase mt-1">Interviews</div>
                </div>
              </div>
            </div>

            <div className="flex gap-4">
              <div className="orion-card p-5 flex-1 pointer-events-auto">
                <div className="flex justify-between items-start mb-2">
                  <h3 className="text-xs font-medium text-white/80">Response Rate</h3>
                </div>
                <div className="text-2xl font-bold mb-4">
                  {stats.response_rate}<span className="text-xs text-[#C1F034] ml-0.5 align-top">%</span>
                </div>
                <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden flex">
                  <div className="h-full bg-[#C1F034] rounded-full" style={{ width: `${Math.min(stats.response_rate, 100)}%` }} />
                </div>
                <div className="flex justify-between mt-2 text-[8px] text-white/40 uppercase">
                  <span>Interviews: {stats.interviews}</span>
                  <span>Rejections: {stats.rejections}</span>
                </div>
              </div>

              <div className="orion-card p-5 flex-[1.2] pointer-events-auto">
                <div className="flex justify-between items-start mb-2">
                  <h3 className="text-xs font-medium text-white/80">Total Applied</h3>
                </div>
                <div className="text-2xl font-bold mb-4">
                  {stats.total_applied}
                </div>
                <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden">
                  <div className="h-full bg-[#C1F034] rounded-full" style={{ width: `${Math.min((stats.total_applied / 100) * 100, 100)}%` }} />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ═══ BOTTOM SECTION ═══ */}
      <div className="mt-16 flex flex-col lg:flex-row items-start gap-8">

        {/* Filters sidebar */}
        <div className="w-full lg:w-[280px] lg:sticky lg:top-8 shrink-0">
          <div className="flex items-center gap-2 mb-6">
            <Filter className="w-5 h-5 text-[#C1F034]" />
            <h2 className="text-xl font-semibold">Matched Jobs</h2>
          </div>
          <div className="orion-card p-5 space-y-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-white/60">Total matched</span>
              <span className="font-bold text-[#C1F034]">{jobs.length}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-white/60">Applied</span>
              <span className="font-bold">{stats.total_applied}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-white/60">Interviews</span>
              <span className="font-bold text-[#C1F034]">{stats.interviews}</span>
            </div>
            <div className="h-px w-full bg-white/10" />
            <p className="text-xs text-white/40 text-center">
              Run a scan to find new job matches
            </p>
          </div>
        </div>

        {/* Job feed */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold">
              Applications{" "}
              <span className="text-sm text-white/40 ml-2 font-normal">{jobs.length} results</span>
            </h2>
            <button className="flex items-center gap-2 text-sm text-white/60 hover:text-white transition-colors bg-white/5 border border-white/10 px-4 py-2 rounded-full backdrop-blur-md cursor-pointer hover:bg-white/10">
              Sort by: Highest Match <ChevronRight className="w-4 h-4 rotate-90" />
            </button>
          </div>

          {loading ? (
            <div className="flex items-center justify-center h-40">
              <Loader2 className="w-8 h-8 animate-spin text-[#C1F034]" />
            </div>
          ) : jobs.length === 0 ? (
            <div className="orion-card p-16 flex flex-col items-center justify-center text-center">
              <Briefcase className="w-12 h-12 text-white/20 mb-4" />
              <h3 className="text-lg font-semibold text-white/60 mb-2">No applications yet</h3>
              <p className="text-sm text-white/40 max-w-md">
                Upload your resume on the Onboarding page, then hit the scan button to start matching and applying to jobs.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 max-h-[800px] overflow-y-auto custom-scroll pr-2 pb-20">
              {jobs
                .sort((a, b) => b.match - a.match)
                .map((job, idx) => (
                  <JobCard key={idx} job={job} />
                ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
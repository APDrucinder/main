"use client";



import {
  ArrowUpRight,
  ChevronRight,
  Heart,
  X,
  Check,
  Filter,
  Play,
  Loader2,
  Activity,
  Briefcase
} from "lucide-react";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import { ApiError } from "@/lib/api-client";
import { getDashboard } from "@/lib/api";
import type { DashboardJob, DashboardResponse } from "@/lib/api-types";

const scanSteps = [
  "Parsing resume...",
  "Scraping jobs...",
  "Filtering...",
  "Auto applying...",
  "Done"
];

function JobCard({ job }: { job: DashboardJob }) {
  const isTopMatch = job.match >= 90 || job.isTop;
  return (
    <div className="orion-card p-5 relative overflow-hidden group hover:border-white/20 transition-colors flex flex-col h-full">
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
        <div className="flex items-center gap-2">
          <button className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center border border-white/10 hover:bg-white/10">
            <Filter className="w-3 h-3 text-white/60" />
          </button>
          <button className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center border border-white/10 hover:bg-white/10">
            <X className="w-3 h-3 text-white/60" />
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mb-8">
        <span className="px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-[10px] font-medium text-white/80">{job.salary}</span>
        <span className="px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-[10px] font-medium text-white/80">{job.type}</span>
        <span className="px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-[10px] font-medium text-white/80">{job.level}</span>
        <span className="px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-[10px] font-medium text-white/80">{job.location}</span>
        <span className="px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-[10px] font-medium text-white/80">{job.locationType}</span>
      </div>

      <div className="flex items-end justify-between mt-auto">
        <div className="flex items-center gap-2 text-xs text-white/40 font-medium">
          <Briefcase className="w-3.5 h-3.5" />
          {job.applicants}
        </div>

        <div className="relative w-20 h-20 flex items-center justify-center shrink-0">
          <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="40" fill="transparent" stroke="rgba(255,255,255,0.1)" strokeWidth="6" />
            <circle cx="50" cy="50" r="40" fill="transparent" stroke="#FFFFFF" strokeWidth="6" strokeDasharray="251.2" strokeDashoffset={251.2 * (1 - job.match / 100)} strokeLinecap="round" />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-xl font-bold text-white leading-none">{job.match}%</span>
            <span className="text-[8px] text-white/70 uppercase font-bold mt-0.5">{isTopMatch ? 'Top Match' : 'Strong Match'}</span>
          </div>
          {job.match >= 85 && (
            <div className="absolute -left-4 top-2 w-6 h-6 rounded-full bg-[#FFFFFF] flex items-center justify-center border-2 border-[#0A0A0A]">
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
export default function DashboardPage() {
  const { isLoaded, isSignedIn } = useUser();
  const router = useRouter();

  const [isScanning, setIsScanning] = useState(false);
  const [scanStep, setScanStep] = useState(0);
  const [dashboardData, setDashboardData] = useState<DashboardResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (isLoaded && !isSignedIn) {
      router.push("/login");
    }
  }, [isLoaded, isSignedIn, router]);

  useEffect(() => {
    if (isScanning && scanStep < scanSteps.length - 1) {
      const timer = setTimeout(() => {
        setScanStep(prev => prev + 1);
      }, 2000);
      return () => clearTimeout(timer);
    } else if (scanStep === scanSteps.length - 1) {
      setTimeout(() => setIsScanning(false), 2000);
    }
  }, [isScanning, scanStep]);

  const startScan = () => {
    setIsScanning(true);
    setScanStep(0);
  };

  useEffect(() => {
    let mounted = true;

    async function loadDashboard() {
      if (!isLoaded || !isSignedIn) return;
      try {
        const data = await getDashboard();
        if (mounted) {
          setDashboardData(data);
          setLoadError(null);
        }
      } catch (error) {
        if (!mounted) return;
        if (error instanceof ApiError) {
          setLoadError(error.message);
        } else {
          setLoadError("Unable to load dashboard data.");
        }
      }
    }

    void loadDashboard();
    return () => {
      mounted = false;
    };
  }, [isLoaded, isSignedIn]);

  const jobs = dashboardData?.jobs ?? [];
  const matched = dashboardData?.matched ?? 0;
  const matchedDelta = dashboardData?.matchedDelta ?? 0;
  const applied = dashboardData?.applied ?? 0;
  const appliedDelta = dashboardData?.appliedDelta ?? 0;
  const interviews = dashboardData?.interviews ?? 0;
  const activeFeeds = dashboardData?.activeFeeds ?? 0;
  const activeFeedsDelta = dashboardData?.activeFeedsDelta ?? 0;
  const successRate = matched > 0 ? ((applied / matched) * 100).toFixed(1) : "0.0";

  if (!isLoaded || !isSignedIn) {
    return <div className="min-h-screen flex items-center justify-center text-white">Loading...</div>;
  }

  return (
    <div className="w-full max-w-[1600px] mx-auto animate-in fade-in duration-700 font-sans mt-2 pb-20 text-white">
      {!dashboardData && !loadError ? (
        <p className="mb-4 rounded-lg border border-white/10 bg-white/[0.03] px-4 py-2 text-xs text-white/60">
          Loading dashboard...
        </p>
      ) : null}
      {loadError ? (
        <p className="mb-4 rounded-lg border border-red-400/20 bg-red-500/10 px-4 py-2 text-xs text-red-200">
          {loadError}
        </p>
      ) : null}

      {/* ═══ HERO SECTION ═══ */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 relative min-h-[480px]">

        {/* Left Area: Title and Salary Chart */}
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
              <h3 className="text-sm font-medium text-white/80">Salary expectations</h3>
              <button className="w-6 h-6 rounded-full bg-white/10 flex items-center justify-center hover:bg-white/20 transition-colors">
                <ArrowUpRight className="w-3 h-3 text-white/60" />
              </button>
            </div>

            <div className="relative h-32 w-full">
              <svg viewBox="0 0 300 100" className="w-full h-full overflow-visible" preserveAspectRatio="none">
                <defs>
                  <pattern id="diagonalHatchDark" width="6" height="6" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
                    <line x1="0" y1="0" x2="0" y2="6" stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
                  </pattern>
                </defs>
                <line x1="0" y1="20" x2="300" y2="20" stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
                <line x1="0" y1="60" x2="300" y2="60" stroke="rgba(255,255,255,0.05)" strokeWidth="1" />

                <polygon points="0,80 50,65 100,75 150,50 200,65 250,30 300,45 300,80 0,80" fill="url(#diagonalHatchDark)" />
                <polyline points="0,80 50,65 100,75 150,50 200,65 250,30 300,45" fill="none" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />

                <circle cx="150" cy="50" r="4" fill="#FFFFFF" />
                <g transform="translate(150, 50)">
                  <rect x="-18" y="-20" width="36" height="14" rx="7" fill="#FFFFFF" />
                  <text x="0" y="-10.5" fontSize="8" fontWeight="bold" fill="black" textAnchor="middle">48%</text>
                </g>
                <circle cx="250" cy="30" r="3" fill="white" />
              </svg>
              <div className="absolute -bottom-2 left-0 right-0 flex justify-between text-[9px] font-semibold text-white/40 uppercase">
                <span>Mar</span><span>Apr</span><span>May</span><span>Jun</span><span>Jul</span><span>Aug</span>
              </div>
              <div className="absolute top-4 -left-8 text-[8px] text-white/40">Senior</div>
              <div className="absolute top-[52px] -left-8 text-[8px] text-white/40">Middle</div>
            </div>
          </div>
        </div>

        {/* Center/Right Area */}
        <div className="lg:col-span-7 relative flex justify-center items-center">

          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] rounded-full pointer-events-none" style={{background: 'radial-gradient(ellipse at center, rgba(160,190,160,0.09) 0%, transparent 65%)', filter: 'blur(80px)'}} />

          <div className="relative z-10 w-full max-w-md orion-card p-8 border border-white/10 glow-neon">
            <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
              <Activity className="w-5 h-5 text-white/70" />
              Agent Operations
            </h2>

            {!isScanning ? (
              <div className="flex flex-col items-center justify-center py-8">
                  <button
                    onClick={startScan}
                    className="w-24 h-24 rounded-full bg-[#FFFFFF] text-black flex items-center justify-center hover:scale-105 transition-transform shadow-[0_0_30px_rgba(255,255,255,0.12)]"
                  >
                    <Play className="w-8 h-8 ml-1" />
                  </button>
                  <p className="mt-6 font-medium text-white/80">Start new scan</p>
                  <p className="text-xs text-white/50 mt-2 text-center max-w-[200px]">Agent will search, filter, and auto-apply based on your settings.</p>
                </div>
              ) : (
                <div className="py-4">
                  <div className="space-y-4">
                    {scanSteps.map((step, idx) => {
                      const isActive = idx === scanStep;
                      const isPast = idx < scanStep;
                      return (
                        <div key={step} className="flex items-center gap-4">
                          <div className={`w-8 h-8 rounded-full flex items-center justify-center border transition-colors ${isPast ? 'bg-white border-white text-black' :
                            isActive ? 'bg-white/10 border-white/60 text-white' : 'bg-transparent border-white/20 text-white/30'
                            }`}>
                            {isPast ? <Check className="w-4 h-4" /> : isActive ? <Loader2 className="w-4 h-4 animate-spin" /> : <div className="w-1.5 h-1.5 rounded-full bg-current" />}
                          </div>
                          <span className={`text-sm font-medium transition-colors ${isPast ? 'text-white' : isActive ? 'text-white' : 'text-white/30'
                            }`}>
                            {step}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
          </div>

          <div className="absolute right-0 top-0 bottom-0 flex flex-col justify-between py-6 w-[320px] pointer-events-none z-20">

            <div className="orion-card p-5 pointer-events-auto">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-sm font-medium">Daily Metrics</h3>
                <button className="w-6 h-6 rounded-full bg-white/10 flex items-center justify-center">
                  <ArrowUpRight className="w-3 h-3 text-white/60" />
                </button>
              </div>
              <div className="flex items-end gap-6 mb-4">
                <div>
                  <div className="text-2xl font-bold stat-number">{matched}<span className="text-[10px] text-white/60 ml-1 align-top">+{matchedDelta}%</span></div>
                  <div className="text-[10px] text-white/50 uppercase mt-1">Matched</div>
                </div>
                <div>
                  <div className="text-2xl font-bold stat-number">{applied}<span className="text-[10px] text-white/60 ml-1 align-top">+{appliedDelta}%</span></div>
                  <div className="text-[10px] text-white/50 uppercase mt-1">Applied</div>
                </div>
                <div>
                  <div className="text-2xl font-bold stat-number">{interviews}<span className="text-[10px] text-white/50 ml-1 align-top"></span></div>
                  <div className="text-[10px] text-white/50 uppercase mt-1">Interviews</div>
                </div>
              </div>
              <div className="flex bg-white/5 rounded-full p-1 border border-white/10 mt-2">
                <div className="flex-1 bg-black rounded-full py-1 text-center text-[10px] font-bold text-white">Jobs</div>
                <div className="flex-1 rounded-full py-1 text-center text-[10px] font-medium text-white/60">Apps</div>
                <div className="flex-1 bg-[#FFFFFF] rounded-full py-1 text-center text-[10px] font-bold text-black">Intvs</div>
              </div>
            </div>

            <div className="flex gap-4">
              <div className="orion-card p-5 flex-1 pointer-events-auto">
                <div className="flex justify-between items-start mb-2">
                  <h3 className="text-xs font-medium text-white/80">Success Rate</h3>
                  <ArrowUpRight className="w-3 h-3 text-white/40" />
                </div>
                <div className="text-2xl font-bold mb-4">
                  {successRate}
                  <span className="text-xs text-white/60 ml-0.5 align-top">%</span>
                </div>
                <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden flex">
                  <div className="h-full bg-white w-1/3"></div>
                  <div className="h-full bg-white/30 w-1/4 ml-1"></div>
                </div>
                <div className="flex justify-between mt-2 text-[8px] text-white/40 uppercase">
                  <span>Interviews</span>
                  <span>Offers</span>
                </div>
              </div>

              <div className="orion-card p-5 flex-[1.2] pointer-events-auto">
                <div className="flex justify-between items-start mb-2">
                  <h3 className="text-xs font-medium text-white/80">Active Feeds</h3>
                  <ArrowUpRight className="w-3 h-3 text-white/40" />
                </div>
                <div className="text-2xl font-bold mb-4">
                  {activeFeeds.toLocaleString()}<span className="text-xs text-white/60 ml-0.5 align-top">+{activeFeedsDelta}</span>
                </div>
                <div className="flex items-end gap-1 h-6">
                  {[40, 70, 45, 90, 60, 30, 80, 100, 50].map((val, i) => (
                    <div key={i} className={`flex-1 rounded-sm ${i === 7 ? 'bg-[#FFFFFF]' : 'bg-white/20'}`} style={{ height: `${val}%` }} />
                  ))}
                </div>
              </div>
            </div>

          </div>

        </div>
      </div>

      {/* ═══ BOTTOM SECTION (SCROLLABLE FEED) ═══ */}
      <div className="mt-16 flex flex-col lg:flex-row items-start gap-8">

        {/* Left Sidebar: Filters */}
        <div className="w-full lg:w-[280px] lg:sticky lg:top-8 shrink-0">
          <div className="flex items-center gap-2 mb-6">
            <Filter className="w-5 h-5 text-white/70" />
            <h2 className="text-xl font-semibold">Filters</h2>
          </div>

          <div className="orion-card p-5 space-y-6">
            <div>
              <h3 className="text-sm font-medium text-white/80 mb-3">Match Score</h3>
              <div className="space-y-2">
                <label className="flex items-center gap-3 cursor-pointer group">
                  <div className="w-4 h-4 rounded border border-white/20 group-hover:border-white flex items-center justify-center bg-white text-black transition-colors">
                    <Check className="w-3 h-3" />
                  </div>
                  <span className="text-sm text-white/70 group-hover:text-white transition-colors">&gt; 80% (Strong Match)</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer group">
                  <div className="w-4 h-4 rounded border border-white/20 group-hover:border-white/50 flex items-center justify-center transition-colors">
                  </div>
                  <span className="text-sm text-white/70 group-hover:text-white transition-colors">60% - 80% (Good Match)</span>
                </label>
              </div>
            </div>

            <div className="h-px w-full bg-white/10" />

            <div>
              <h3 className="text-sm font-medium text-white/80 mb-3">Job Type</h3>
              <div className="flex flex-wrap gap-2">
                <button className="glass-pill-active px-3 py-1.5 text-xs font-medium cursor-pointer">Remote</button>
                <button className="glass-pill px-3 py-1.5 text-xs font-medium cursor-pointer hover:bg-white/10 transition-colors">Hybrid</button>
                <button className="glass-pill px-3 py-1.5 text-xs font-medium cursor-pointer hover:bg-white/10 transition-colors">On-site</button>
              </div>
            </div>

            <div className="h-px w-full bg-white/10" />

            <div>
              <h3 className="text-sm font-medium text-white/80 mb-3">Seniority Level</h3>
              <div className="space-y-2">
                <label className="flex items-center gap-3 cursor-pointer group">
                  <div className="w-4 h-4 rounded border border-white/20 group-hover:border-white/50 flex items-center justify-center transition-colors"></div>
                  <span className="text-sm text-white/70 group-hover:text-white transition-colors">Junior</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer group">
                  <div className="w-4 h-4 rounded border border-white/20 group-hover:border-white flex items-center justify-center bg-white text-black transition-colors"><Check className="w-3 h-3" /></div>
                  <span className="text-sm text-white/70 group-hover:text-white transition-colors">Middle</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer group">
                  <div className="w-4 h-4 rounded border border-white/20 group-hover:border-white flex items-center justify-center bg-white text-black transition-colors"><Check className="w-3 h-3" /></div>
                  <span className="text-sm text-white/70 group-hover:text-white transition-colors">Senior</span>
                </label>
              </div>
            </div>

            <div className="h-px w-full bg-white/10" />

            <div>
              <h3 className="text-sm font-medium text-white/80 mb-3">Salary Range</h3>
              <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden mt-4">
                <div className="w-1/2 h-full bg-[#FFFFFF] ml-1/4"></div>
              </div>
              <div className="flex justify-between mt-2 text-xs text-white/50">
                <span>$80k</span>
                <span>$150k</span>
              </div>
            </div>

          </div>
        </div>

        {/* Right Scrollable Feed: Jobs */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold">Matched Jobs <span className="text-sm text-white/40 ml-2 font-normal">{jobs.length} results</span></h2>
            <button className="flex items-center gap-2 text-sm text-white/60 hover:text-white transition-colors bg-white/5 border border-white/10 px-4 py-2 rounded-full backdrop-blur-md cursor-pointer hover:bg-white/10">
              Sort by: Highest Match <ChevronRight className="w-4 h-4 rotate-90" />
            </button>
          </div>

          {jobs.length > 0 ? (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 h-[800px] overflow-y-auto custom-scroll pr-2 pb-20">
              {jobs.map((job, idx) => (
                <JobCard key={`${job.company}-${job.title}-${idx}`} job={job} />
              ))}
            </div>
          ) : (
            <div className="orion-card flex h-80 flex-col items-center justify-center px-6 text-center">
              <Briefcase className="mb-4 h-8 w-8 text-white/35" />
              <h3 className="text-lg font-semibold text-white">No matched jobs yet</h3>
              <p className="mt-2 max-w-md text-sm text-white/45">
                Start a scan after completing onboarding to populate this feed with real matches.
              </p>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}

"use client";

import {
  Briefcase,
  Search,
  Filter,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Clock,
  MoreVertical,
  ExternalLink,
  ThumbsUp,
  ThumbsDown,
  MessageSquare
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { ApiError } from "@/lib/api-client";
import { getApplications } from "@/lib/api";
import type { Application } from "@/lib/api-types";

const fallbackApplications: Application[] = [
  { id: 1, company: "Amazon", role: "Frontend Engineer", score: 88, status: "Applied", platform: "LinkedIn", date: "Today", feedback: null },
  { id: 2, company: "Google", role: "UX Engineer", score: 92, status: "Manual Required", platform: "Greenhouse", date: "Today", feedback: null },
  { id: 3, company: "Stripe", role: "Product Designer", score: 75, status: "Below Threshold", platform: "Lever", date: "Yesterday", feedback: null },
  { id: 4, company: "Vercel", role: "Design Engineer", score: 95, status: "Applied", platform: "Workday", date: "2 days ago", feedback: "Got Interview" },
  { id: 5, company: "Meta", role: "UI Developer", score: 82, status: "Failed", platform: "Meta Careers", date: "3 days ago", feedback: null },
  { id: 6, company: "Netflix", role: "Senior Designer", score: 89, status: "Needs Credentials", platform: "Workday", date: "4 days ago", feedback: null },
];
export default function ApplicationsPage() {
  const [applications, setApplications] = useState<Application[]>(fallbackApplications);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    async function loadApplications() {
      try {
        const data = await getApplications();
        if (mounted) {
          setApplications(data);
          setLoadError(null);
        }
      } catch (error) {
        if (!mounted) return;
        setLoadError(error instanceof ApiError ? error.message : "Unable to load applications.");
      } finally {
        if (mounted) setLoading(false);
      }
    }

    void loadApplications();
    return () => {
      mounted = false;
    };
  }, []);

  const stats = useMemo(() => {
    const total = applications.length;
    const interviews = applications.filter((app) => app.feedback?.toLowerCase().includes("interview")).length;
    const failedOrManual = applications.filter((app) =>
      app.status === "Failed" || app.status === "Manual Required"
    ).length;
    const applied = applications.filter((app) => app.status === "Applied").length;
    const successRate = total > 0 ? `${((applied / total) * 100).toFixed(1)}%` : "0.0%";

    return { total, interviews, failedOrManual, successRate };
  }, [applications]);

  const getStatusConfig = (status: string) => {
    switch (status) {
      case "Applied": return { icon: CheckCircle2, color: "text-[#C1F034]", bg: "bg-[#C1F034]/10" };
      case "Matched": return { icon: Clock, color: "text-blue-400", bg: "bg-blue-400/10" };
      case "Failed": return { icon: XCircle, color: "text-red-400", bg: "bg-red-400/10" };
      case "Manual Required": return { icon: AlertCircle, color: "text-orange-400", bg: "bg-orange-400/10" };
      case "Needs Credentials": return { icon: AlertCircle, color: "text-yellow-400", bg: "bg-yellow-400/10" };
      case "Below Threshold": return { icon: Filter, color: "text-white/40", bg: "bg-white/5" };
      default: return { icon: Clock, color: "text-white/60", bg: "bg-white/10" };
    }
  };

  return (
    <div className="w-full max-w-[1400px] mx-auto animate-in fade-in duration-700 font-sans mt-8 pb-20 text-white">
      {loading ? (
        <p className="mb-4 rounded-lg border border-white/10 bg-white/[0.03] px-4 py-2 text-xs text-white/60">
          Loading applications...
        </p>
      ) : null}
      {loadError ? (
        <p className="mb-4 rounded-lg border border-red-400/20 bg-red-500/10 px-4 py-2 text-xs text-red-200">
          {loadError}
        </p>
      ) : null}

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <h1 className="text-4xl font-light tracking-tight leading-tight uppercase">
            APPLICATION <span className="font-bold">TRACKER</span>
          </h1>
          <p className="text-white/50 mt-2">Monitor your AI agent&apos;s application pipeline and statuses.</p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center bg-white/5 border border-white/10 rounded-full px-4 py-2">
            <Search className="w-4 h-4 text-white/40 mr-2" />
            <input type="text" placeholder="Search applications..." className="bg-transparent border-none outline-none text-sm text-white w-48" />
          </div>
          <button className="flex items-center gap-2 px-4 py-2 bg-white/5 border border-white/10 rounded-full text-sm font-semibold hover:bg-white/10 transition-colors">
            <Filter className="w-4 h-4" /> Filter
          </button>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {[
          { label: "Total Sent", value: String(stats.total) },
          { label: "Interviews", value: String(stats.interviews), color: "text-[#C1F034]" },
          { label: "Failed/Manual", value: String(stats.failedOrManual), color: "text-orange-400" },
          { label: "Success Rate", value: stats.successRate }
        ].map((stat, i) => (
          <div key={i} className="orion-card p-4">
            <p className="text-xs font-medium text-white/50 uppercase mb-1">{stat.label}</p>
            <p className={`text-2xl font-bold stat-number ${stat.color || "text-white"}`}>{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Tracker List */}
      <div className="orion-card overflow-hidden">

        {/* Table Header */}
        <div className="grid grid-cols-12 gap-4 p-4 border-b border-white/10 bg-white/5 text-xs font-medium text-white/50 uppercase tracking-wider">
          <div className="col-span-3">Company & Role</div>
          <div className="col-span-2 text-center">Score</div>
          <div className="col-span-2">Status</div>
          <div className="col-span-2">Platform</div>
          <div className="col-span-2">Feedback</div>
          <div className="col-span-1 text-right">Actions</div>
        </div>

        {/* Table Body */}
        <div className="divide-y divide-white/5">
          {applications.map((app) => {
            const StatusIcon = getStatusConfig(app.status).icon;

            return (
              <div key={app.id} className="grid grid-cols-12 gap-4 p-4 items-center hover:bg-white/5 transition-colors group">

                {/* Company & Role */}
                <div className="col-span-3 flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-white/10 border border-white/10 flex items-center justify-center">
                    <Briefcase className="w-5 h-5 text-white/60" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-white">{app.company}</h3>
                    <p className="text-xs text-white/50">{app.role}</p>
                  </div>
                </div>

                {/* Score */}
                <div className="col-span-2 flex items-center justify-center">
                  <div className="relative w-10 h-10 flex items-center justify-center">
                    <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                      <circle cx="50" cy="50" r="40" fill="transparent" stroke="rgba(255,255,255,0.1)" strokeWidth="8" />
                      <circle cx="50" cy="50" r="40" fill="transparent" stroke={app.score >= 80 ? "#C1F034" : "#38BDF8"} strokeWidth="8" strokeDasharray="251.2" strokeDashoffset={251.2 * (1 - app.score / 100)} strokeLinecap="round" />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-[10px] font-bold">{app.score}</span>
                    </div>
                  </div>
                </div>

                {/* Status */}
                <div className="col-span-2">
                  <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold border border-white/5 ${getStatusConfig(app.status).bg} ${getStatusConfig(app.status).color}`}>
                    <StatusIcon className="w-3 h-3" />
                    {app.status}
                  </span>
                  <p className="text-[10px] text-white/40 mt-1 ml-1">{app.date}</p>
                </div>

                {/* Platform */}
                <div className="col-span-2">
                  <span className="text-xs text-white/80">{app.platform}</span>
                </div>

                {/* Feedback */}
                <div className="col-span-2">
                  {app.feedback ? (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#C1F034]/20 border border-[#C1F034]/30 text-[#C1F034] text-[10px] font-bold">
                      <MessageSquare className="w-3 h-3" />
                      {app.feedback}
                    </span>
                  ) : (
                    <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button className="w-6 h-6 rounded bg-white/10 flex items-center justify-center hover:bg-[#C1F034]/20 hover:text-[#C1F034] transition-colors" title="Got Interview">
                        <ThumbsUp className="w-3 h-3" />
                      </button>
                      <button className="w-6 h-6 rounded bg-white/10 flex items-center justify-center hover:bg-red-500/20 hover:text-red-400 transition-colors" title="Rejected">
                        <ThumbsDown className="w-3 h-3" />
                      </button>
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="col-span-1 flex items-center justify-end gap-2">
                  <button className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-white/10 text-white/40 hover:text-white transition-colors">
                    <ExternalLink className="w-4 h-4" />
                  </button>
                  <button className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-white/10 text-white/40 hover:text-white transition-colors">
                    <MoreVertical className="w-4 h-4" />
                  </button>
                </div>

              </div>
            );
          })}
        </div>

      </div>
    </div>
  );
}

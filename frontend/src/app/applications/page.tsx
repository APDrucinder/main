"use client";

import {
  Briefcase,
  Search,
  Filter,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Clock,
  ExternalLink,
  ThumbsUp,
  ThumbsDown,
  MessageSquare,
  Loader2,
} from "lucide-react";
import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

export default function ApplicationsPage() {
  const [applications, setApplications] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [stats, setStats] = useState({
    total_applied: 0,
    interviews: 0,
    rejections: 0,
    response_rate: 0,
  });

  const loadData = useCallback(async () => {
    try {
      const [appData, statsData] = await Promise.all([
        api.getApplications(),
        api.getStats(),
      ]);

      if (appData && Array.isArray(appData.applications)) {
        setApplications(appData.applications);
      }

      if (statsData) {
        setStats({
          total_applied: statsData.total_applied ?? 0,
          interviews: statsData.interviews ?? 0,
          rejections: statsData.rejections ?? 0,
          response_rate: statsData.response_rate_percent ?? 0,
        });
      }
    } catch {
      // Keep defaults
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleFeedback = async (applicationId: string, feedback: "got_interview" | "rejected") => {
    try {
      await api.submitFeedback(applicationId, feedback);
      // Update local state
      setApplications(prev =>
        prev.map(app =>
          app.application_id === applicationId
            ? { ...app, feedback: feedback === "got_interview" ? "Got Interview" : "Rejected", status: feedback === "got_interview" ? "interview" : "rejected" }
            : app
        )
      );
      // Refresh stats
      const newStats = await api.getStats();
      if (newStats) {
        setStats({
          total_applied: newStats.total_applied ?? 0,
          interviews: newStats.interviews ?? 0,
          rejections: newStats.rejections ?? 0,
          response_rate: newStats.response_rate_percent ?? 0,
        });
      }
    } catch {
      // Silently fail
    }
  };

  const getStatusConfig = (status: string) => {
    switch (status) {
      case "applied": return { icon: CheckCircle2, color: "text-[#C1F034]", bg: "bg-[#C1F034]/10" };
      case "matched": return { icon: Clock, color: "text-blue-400", bg: "bg-blue-400/10" };
      case "failed": return { icon: XCircle, color: "text-red-400", bg: "bg-red-400/10" };
      case "manual_required": return { icon: AlertCircle, color: "text-orange-400", bg: "bg-orange-400/10" };
      case "interview": return { icon: CheckCircle2, color: "text-[#C1F034]", bg: "bg-[#C1F034]/10" };
      case "rejected": return { icon: XCircle, color: "text-red-400", bg: "bg-red-400/10" };
      default: return { icon: Clock, color: "text-white/60", bg: "bg-white/10" };
    }
  };

  const filteredApps = applications.filter(app => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      (app.job?.title || "").toLowerCase().includes(q) ||
      (app.job?.company || "").toLowerCase().includes(q)
    );
  });

  if (loading) {
    return (
      <div className="w-full max-w-[1400px] mx-auto flex items-center justify-center h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-[#C1F034]" />
      </div>
    );
  }

  return (
    <div className="w-full max-w-[1400px] mx-auto animate-in fade-in duration-700 font-sans mt-8 pb-20 text-white">

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
            <input
              type="text"
              placeholder="Search applications..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="bg-transparent border-none outline-none text-sm text-white w-48"
            />
          </div>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {[
          { label: "Total Sent", value: stats.total_applied.toString() },
          { label: "Interviews", value: stats.interviews.toString(), color: "text-[#C1F034]" },
          { label: "Rejections", value: stats.rejections.toString(), color: "text-red-400" },
          { label: "Response Rate", value: `${stats.response_rate}%` },
        ].map((stat, i) => (
          <div key={i} className="orion-card p-4">
            <p className="text-xs font-medium text-white/50 uppercase mb-1">{stat.label}</p>
            <p className={`text-2xl font-bold stat-number ${stat.color || "text-white"}`}>{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Tracker List */}
      {filteredApps.length === 0 ? (
        <div className="orion-card p-16 flex flex-col items-center justify-center text-center">
          <Briefcase className="w-12 h-12 text-white/20 mb-4" />
          <h3 className="text-lg font-semibold text-white/60 mb-2">
            {searchQuery ? "No matching applications" : "No applications yet"}
          </h3>
          <p className="text-sm text-white/40 max-w-md">
            {searchQuery
              ? "Try a different search term."
              : "Run a scan from the Dashboard to start matching and applying to jobs."}
          </p>
        </div>
      ) : (
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
            {filteredApps.map((app) => {
              const statusConfig = getStatusConfig(app.status);
              const StatusIcon = statusConfig.icon;

              return (
                <div key={app.application_id} className="grid grid-cols-12 gap-4 p-4 items-center hover:bg-white/5 transition-colors group">

                  {/* Company & Role */}
                  <div className="col-span-3 flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-white/10 border border-white/10 flex items-center justify-center">
                      <span className="font-bold text-white/60 text-sm">
                        {(app.job?.company || "?")[0].toUpperCase()}
                      </span>
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-white">{app.job?.company || "Unknown"}</h3>
                      <p className="text-xs text-white/50">{app.job?.title || "Unknown Role"}</p>
                    </div>
                  </div>

                  {/* Score */}
                  <div className="col-span-2 flex items-center justify-center">
                    <div className="relative w-10 h-10 flex items-center justify-center">
                      <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                        <circle cx="50" cy="50" r="40" fill="transparent" stroke="rgba(255,255,255,0.1)" strokeWidth="8" />
                        <circle cx="50" cy="50" r="40" fill="transparent" stroke={(app.match_score || 0) >= 80 ? "#C1F034" : "#38BDF8"} strokeWidth="8" strokeDasharray="251.2" strokeDashoffset={251.2 * (1 - (app.match_score || 0) / 100)} strokeLinecap="round" />
                      </svg>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <span className="text-[10px] font-bold">{app.match_score || 0}</span>
                      </div>
                    </div>
                  </div>

                  {/* Status */}
                  <div className="col-span-2">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold border border-white/5 ${statusConfig.bg} ${statusConfig.color}`}>
                      <StatusIcon className="w-3 h-3" />
                      {app.status}
                    </span>
                    <p className="text-[10px] text-white/40 mt-1 ml-1">
                      {app.applied_at ? new Date(app.applied_at).toLocaleDateString() : "—"}
                    </p>
                  </div>

                  {/* Platform */}
                  <div className="col-span-2">
                    <span className="text-xs text-white/80">{app.job?.source || "—"}</span>
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
                        <button
                          onClick={() => handleFeedback(app.application_id, "got_interview")}
                          className="w-6 h-6 rounded bg-white/10 flex items-center justify-center hover:bg-[#C1F034]/20 hover:text-[#C1F034] transition-colors"
                          title="Got Interview"
                        >
                          <ThumbsUp className="w-3 h-3" />
                        </button>
                        <button
                          onClick={() => handleFeedback(app.application_id, "rejected")}
                          className="w-6 h-6 rounded bg-white/10 flex items-center justify-center hover:bg-red-500/20 hover:text-red-400 transition-colors"
                          title="Rejected"
                        >
                          <ThumbsDown className="w-3 h-3" />
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="col-span-1 flex items-center justify-end gap-2">
                    {app.job?.apply_url && (
                      <a
                        href={app.job.apply_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-white/10 text-white/40 hover:text-white transition-colors"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    )}
                  </div>

                </div>
              );
            })}
          </div>

        </div>
      )}
    </div>
  );
}

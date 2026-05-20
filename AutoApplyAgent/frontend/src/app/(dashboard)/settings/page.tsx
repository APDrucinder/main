"use client";

import {
  User,
  Settings2,
  CreditCard,
  Bell,
  Shield,
  Briefcase,
  AlertCircle,
  RefreshCw
} from "lucide-react";
import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api-client";
import { getPlatformSessions, updateSettings } from "@/lib/api";
import type { PlatformSession } from "@/lib/api-types";

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState("agent");
  const [targetRoles, setTargetRoles] = useState("");
  const [locations, setLocations] = useState("");
  const [experienceRange, setExperienceRange] = useState("0-1");
  const [minSalary, setMinSalary] = useState("");
  const [autoApplyThreshold, setAutoApplyThreshold] = useState(75);
  const [remoteFlexibility, setRemoteFlexibility] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [sessions, setSessions] = useState<PlatformSession[]>([]);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);

  async function loadPlatformSessions() {
    setSessionLoading(true);
    setSessionError(null);
    try {
      const response = await getPlatformSessions();
      setSessions(response.sessions);
    } catch (error) {
      setSessionError(error instanceof ApiError ? error.message : "Unable to load platform sessions.");
    } finally {
      setSessionLoading(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadPlatformSessions();
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  async function handleSaveSettings() {
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(null);
    try {
      await updateSettings({
        targetRoles,
        locations,
        experienceRange,
        minSalary,
        autoApplyThreshold,
        remoteFlexibility,
      });
      setSaveSuccess("Settings saved.");
    } catch (error) {
      setSaveError(error instanceof ApiError ? error.message : "Unable to save settings.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="w-full max-w-[1200px] mx-auto animate-in fade-in duration-700 font-sans mt-8 pb-20 text-white">

      <div className="mb-12">
        <h1 className="text-4xl font-light tracking-tight leading-tight mb-2 uppercase">
          SYSTEM <span className="font-bold">SETTINGS</span>
        </h1>
        <p className="text-white/50">Manage your subscription, agent parameters, and notifications.</p>
      </div>

      <div className="flex flex-col md:flex-row gap-8">

        {/* Settings Sidebar */}
        <div className="w-full md:w-64 space-y-2 flex-shrink-0">
          {[
            { id: "agent", icon: Settings2, label: "Agent Preferences" },
            { id: "billing", icon: CreditCard, label: "Subscription & Billing" },
            { id: "notifications", icon: Bell, label: "Notifications" },
            { id: "account", icon: User, label: "Account Details" },
            { id: "security", icon: Shield, label: "Security & Privacy" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${activeTab === tab.id
                ? "bg-white text-black shadow-[0_0_12px_rgba(255,255,255,0.06)]"
                : "text-white/60 hover:bg-white/5 hover:text-white"
                }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Settings Content */}
        <div className="flex-1 space-y-6">

          {/* Agent Preferences Tab */}
          {activeTab === "agent" && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-500">
              <div className="orion-card p-6 mb-6">
                <h2 className="text-lg font-semibold mb-6 flex items-center gap-2">
                  <Briefcase className="w-5 h-5 text-white" /> Search Parameters
                </h2>
                <div className="space-y-6">
                  <div className="grid grid-cols-2 gap-6">
                    <div>
                      <label className="text-xs font-medium text-white/60 uppercase mb-2 block">Target Roles</label>
                      <input type="text" value={targetRoles} onChange={(e) => setTargetRoles(e.target.value)} placeholder="Frontend Engineer, Product Designer" className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder:text-white/25 focus:border-white/50" />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-white/60 uppercase mb-2 block">Locations</label>
                      <input type="text" value={locations} onChange={(e) => setLocations(e.target.value)} placeholder="Remote, New York, Bengaluru" className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder:text-white/25 focus:border-white/50" />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-6">
                    <div>
                      <label className="text-xs font-medium text-white/60 uppercase mb-2 block">Years of Experience</label>
                      <select value={experienceRange} onChange={(e) => setExperienceRange(e.target.value)} className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-white/50 appearance-none">
                        <option value="0-1">0 - 1 Years</option>
                        <option value="1-3">1 - 3 Years</option>
                        <option value="3-5">3 - 5 Years</option>
                        <option value="5+">5+ Years</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs font-medium text-white/60 uppercase mb-2 block">Min Salary</label>
                      <input type="text" value={minSalary} onChange={(e) => setMinSalary(e.target.value)} placeholder="100000" className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder:text-white/25 focus:border-white/50" />
                    </div>
                  </div>
                </div>
              </div>

              <div className="orion-card p-6">
                <h2 className="text-lg font-semibold mb-6 flex items-center gap-2">
                  <Settings2 className="w-5 h-5 text-white" /> Automation Rules
                </h2>
                <div className="space-y-6">
                  <div>
                    <div className="flex justify-between items-end mb-4">
                      <label className="text-xs font-medium text-white/60 uppercase">Auto-Apply Threshold</label>
                      <span className="text-lg font-bold text-white">{autoApplyThreshold}%</span>
                    </div>
                    <input type="range" min="75" max="95" value={autoApplyThreshold} onChange={(e) => setAutoApplyThreshold(parseInt(e.target.value, 10))} className="w-full" />
                    <div className="mt-3 flex items-start gap-2 rounded-lg bg-white/5 border border-white/10 px-3 py-2.5">
                      <AlertCircle className="w-3.5 h-3.5 text-white/50 mt-0.5 flex-shrink-0" />
                      <p className="text-xs text-white/50 leading-relaxed">
                        <span className="font-semibold text-white/70">Conservative mode</span> — No service can guarantee a platform will never flag automation. Celerix uses stricter match thresholds, per-run caps, and pauses when a platform session looks invalid.
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center justify-between py-4 border-t border-white/10">
                    <div>
                      <h3 className="text-sm font-semibold text-white">Remote Flexibility</h3>
                      <p className="text-xs text-white/50">Prioritize fully remote roles over hybrid/onsite</p>
                    </div>
                    <button type="button" onClick={() => setRemoteFlexibility((prev) => !prev)} className={`w-12 h-6 rounded-full relative cursor-pointer border shadow-[0_0_12px_rgba(255,255,255,0.06)] ${remoteFlexibility ? "bg-white border-white/20" : "bg-white/10 border-white/20"}`}>
                      <div className={`absolute top-1 w-4 h-4 bg-black rounded-full shadow-sm transition-all ${remoteFlexibility ? "right-1" : "left-1"}`}></div>
                    </button>
                  </div>
                  <div className="border-t border-white/10 pt-5">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <div>
                        <h3 className="text-sm font-semibold text-white">Platform Sessions</h3>
                        <p className="text-xs text-white/50">Live LinkedIn auto-apply needs a valid server-side session capture.</p>
                      </div>
                      <button
                        type="button"
                        onClick={loadPlatformSessions}
                        disabled={sessionLoading}
                        className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-white/70 hover:bg-white/10 disabled:opacity-50"
                        title="Refresh session status"
                      >
                        <RefreshCw className={`h-4 w-4 ${sessionLoading ? "animate-spin" : ""}`} />
                      </button>
                    </div>
                    {sessionError ? <p className="mb-3 text-xs text-red-300">{sessionError}</p> : null}
                    <div className="space-y-2">
                      {sessions.filter((session) => session.platform === "linkedin").map((session) => (
                        <div key={session.platform} className="rounded-lg border border-white/10 bg-white/5 px-3 py-3">
                          <div className="flex items-center justify-between gap-3">
                            <span className="text-sm font-semibold capitalize text-white">{session.platform}</span>
                            <span className={`rounded-full px-2 py-1 text-[11px] font-semibold uppercase ${
                              session.state === "available" ? "bg-emerald-400/15 text-emerald-200" : "bg-amber-400/15 text-amber-200"
                            }`}>
                              {session.state}
                            </span>
                          </div>
                          <p className="mt-2 text-xs leading-relaxed text-white/50">{session.message}</p>
                          {session.captured_at ? (
                            <p className="mt-2 text-[11px] text-white/35">
                              Captured {new Date(session.captured_at).toLocaleString()} with {session.cookie_count} cookies
                            </p>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="pt-3">
                    <button
                      type="button"
                      onClick={handleSaveSettings}
                      disabled={saving}
                      className="w-full rounded-xl bg-white px-4 py-3 text-sm font-semibold text-black hover:bg-zinc-200 disabled:cursor-not-allowed disabled:opacity-70"
                    >
                      {saving ? "Saving..." : "Save Settings"}
                    </button>
                    {saveError ? <p className="mt-3 text-xs text-red-300">{saveError}</p> : null}
                    {saveSuccess ? <p className="mt-3 text-xs text-white">{saveSuccess}</p> : null}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Subscription Tab */}
          {activeTab === "billing" && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-500">

              <div className="orion-card p-6 relative overflow-hidden mb-6 border-white/10">
                <div className="flex items-start gap-4">
                  <AlertCircle className="mt-1 h-5 w-5 text-white/45" />
                  <div>
                    <h2 className="text-xl font-semibold">Billing is not connected</h2>
                    <p className="mt-2 max-w-xl text-sm text-white/50">
                      Connect a billing provider before showing subscription plans, renewal dates, prices, or usage limits.
                    </p>
                  </div>
                </div>
              </div>

            </div>
          )}

          {/* Notifications Tab */}
          {activeTab === "notifications" && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-500">
              <div className="orion-card p-6">
                <h2 className="text-lg font-semibold mb-6 flex items-center gap-2">
                  <Bell className="w-5 h-5 text-white" /> Notification Channels
                </h2>

                <div className="space-y-4">
                  {[
                    { title: "Daily Digest Email", desc: "Summary of matches and applications sent every morning.", defaultChecked: true },
                    { title: "WhatsApp Digest", desc: "Instant alerts for interviews and critical errors.", defaultChecked: true, badge: "Pro" },
                    { title: "In-app Toasts", desc: "Popups when a scan completes while you are online.", defaultChecked: true },
                    { title: "Manual Intervention Alerts", desc: "Get notified when an application needs your manual input or credentials.", defaultChecked: true },
                  ].map((notif, idx) => (
                    <div key={idx} className="flex items-center justify-between p-4 bg-white/5 rounded-xl border border-white/10">
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-semibold text-white">{notif.title}</h3>
                          {notif.badge && <span className="text-[9px] font-bold uppercase bg-white/20 text-white px-1.5 py-0.5 rounded border border-white/30">{notif.badge}</span>}
                        </div>
                        <p className="text-xs text-white/50 mt-1">{notif.desc}</p>
                      </div>
                      <div className={`w-10 h-5 rounded-full relative cursor-pointer border ${notif.defaultChecked ? 'bg-white border-white/20' : 'bg-white/10 border-white/10'}`}>
                        <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-black shadow-sm transition-all ${notif.defaultChecked ? 'right-0.5' : 'left-0.5'}`}></div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}

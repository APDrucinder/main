"use client";

import {
  User,
  Settings2,
  CreditCard,
  Bell,
  Shield,
  Briefcase,
  Zap,
  AlertCircle
} from "lucide-react";
import { useState } from "react";
import { ApiError } from "@/lib/api-client";
import { updateSettings } from "@/lib/api";

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState("agent");
  const [targetRoles, setTargetRoles] = useState("Web Designer, UX/UI Designer");
  const [locations, setLocations] = useState("Los Angeles, CA, Remote");
  const [experienceRange, setExperienceRange] = useState("3-5");
  const [minSalary, setMinSalary] = useState("$110,000");
  const [autoApplyThreshold, setAutoApplyThreshold] = useState(80);
  const [remoteFlexibility, setRemoteFlexibility] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);

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
                ? "bg-[#C1F034] text-black shadow-[0_0_15px_rgba(193,240,52,0.2)]"
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
                  <Briefcase className="w-5 h-5 text-[#C1F034]" /> Search Parameters
                </h2>
                <div className="space-y-6">
                  <div className="grid grid-cols-2 gap-6">
                    <div>
                      <label className="text-xs font-medium text-white/60 uppercase mb-2 block">Target Roles</label>
                      <input type="text" value={targetRoles} onChange={(e) => setTargetRoles(e.target.value)} className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-[#C1F034]/50" />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-white/60 uppercase mb-2 block">Locations</label>
                      <input type="text" value={locations} onChange={(e) => setLocations(e.target.value)} className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-[#C1F034]/50" />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-6">
                    <div>
                      <label className="text-xs font-medium text-white/60 uppercase mb-2 block">Years of Experience</label>
                      <select value={experienceRange} onChange={(e) => setExperienceRange(e.target.value)} className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-[#C1F034]/50 appearance-none">
                        <option value="3-5">3 - 5 Years</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs font-medium text-white/60 uppercase mb-2 block">Min Salary</label>
                      <input type="text" value={minSalary} onChange={(e) => setMinSalary(e.target.value)} className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-[#C1F034]/50" />
                    </div>
                  </div>
                </div>
              </div>

              <div className="orion-card p-6">
                <h2 className="text-lg font-semibold mb-6 flex items-center gap-2">
                  <Settings2 className="w-5 h-5 text-[#C1F034]" /> Automation Rules
                </h2>
                <div className="space-y-6">
                  <div>
                    <div className="flex justify-between items-end mb-4">
                      <label className="text-xs font-medium text-white/60 uppercase">Auto-Apply Threshold</label>
                      <span className="text-lg font-bold text-[#C1F034]">{autoApplyThreshold}%</span>
                    </div>
                    <input type="range" min="50" max="90" value={autoApplyThreshold} onChange={(e) => setAutoApplyThreshold(parseInt(e.target.value, 10))} className="w-full" />
                  </div>
                  <div className="flex items-center justify-between py-4 border-t border-white/10">
                    <div>
                      <h3 className="text-sm font-semibold text-white">Remote Flexibility</h3>
                      <p className="text-xs text-white/50">Prioritize fully remote roles over hybrid/onsite</p>
                    </div>
                    <button type="button" onClick={() => setRemoteFlexibility((prev) => !prev)} className={`w-12 h-6 rounded-full relative cursor-pointer border shadow-[0_0_15px_rgba(193,240,52,0.2)] ${remoteFlexibility ? "bg-[#C1F034] border-[#C1F034]/20" : "bg-white/10 border-white/20"}`}>
                      <div className={`absolute top-1 w-4 h-4 bg-black rounded-full shadow-sm transition-all ${remoteFlexibility ? "right-1" : "left-1"}`}></div>
                    </button>
                  </div>
                  <div className="pt-3">
                    <button
                      type="button"
                      onClick={handleSaveSettings}
                      disabled={saving}
                      className="w-full rounded-xl bg-[#C1F034] px-4 py-3 text-sm font-semibold text-black hover:bg-[#A3E635] disabled:cursor-not-allowed disabled:opacity-70"
                    >
                      {saving ? "Saving..." : "Save Settings"}
                    </button>
                    {saveError ? <p className="mt-3 text-xs text-red-300">{saveError}</p> : null}
                    {saveSuccess ? <p className="mt-3 text-xs text-[#C1F034]">{saveSuccess}</p> : null}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Subscription Tab */}
          {activeTab === "billing" && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-500">

              <div className="orion-card p-6 relative overflow-hidden mb-6 border-[#C1F034]/30">
                <div className="absolute top-0 right-0 w-64 h-64 bg-[#C1F034]/10 blur-3xl rounded-full translate-x-1/2 -translate-y-1/2" />
                <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
                  <div>
                    <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#C1F034]/20 border border-[#C1F034]/30 text-[#C1F034] text-xs font-bold mb-4 uppercase tracking-wider">
                      <Zap className="w-3.5 h-3.5 fill-[#C1F034]" /> Pro Plan
                    </div>
                    <h2 className="text-3xl font-light mb-1">Active Subscription</h2>
                    <p className="text-sm text-white/60">Your plan renews on May 28, 2026</p>
                  </div>
                  <div className="text-left md:text-right">
                    <p className="text-4xl font-bold tracking-tight mb-1">$49<span className="text-lg font-medium text-white/50">/mo</span></p>
                    <button className="px-6 py-2 bg-white text-black font-semibold rounded-full hover:bg-white/90 transition-colors mt-4 text-sm">
                      Manage Billing
                    </button>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                <div className="orion-card p-6">
                  <div className="flex justify-between items-start mb-4">
                    <h3 className="text-sm font-semibold">Daily Applications Limit</h3>
                    <AlertCircle className="w-4 h-4 text-orange-400" />
                  </div>
                  <div className="flex items-end gap-2 mb-4">
                    <span className="text-3xl font-bold text-white">45</span>
                    <span className="text-sm font-medium text-white/40 mb-1">/ 50</span>
                  </div>
                  <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden">
                    <div className="h-full bg-orange-400 w-[90%] rounded-full"></div>
                  </div>
                  <p className="text-xs text-white/50 mt-4 text-center">Approaching daily safety limit.</p>
                </div>

                <div className="orion-card p-6 flex flex-col justify-center items-center text-center border-dashed border-white/20 bg-transparent hover:bg-white/5 transition-colors cursor-pointer group">
                  <div className="w-12 h-12 rounded-full bg-white/5 border border-white/10 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                    <Zap className="w-6 h-6 text-[#C1F034]" />
                  </div>
                  <h3 className="text-lg font-bold mb-2 text-white">Need more volume?</h3>
                  <p className="text-sm text-white/50 mb-4 px-4">Upgrade to Power User tier for 200 daily applications.</p>
                  <button className="px-6 py-2 bg-[#C1F034] text-black font-semibold rounded-full shadow-[0_0_15px_rgba(193,240,52,0.3)] hover:scale-105 transition-transform text-sm">
                    Upgrade Plan
                  </button>
                </div>
              </div>

            </div>
          )}

          {/* Notifications Tab */}
          {activeTab === "notifications" && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-500">
              <div className="orion-card p-6">
                <h2 className="text-lg font-semibold mb-6 flex items-center gap-2">
                  <Bell className="w-5 h-5 text-[#C1F034]" /> Notification Channels
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
                          {notif.badge && <span className="text-[9px] font-bold uppercase bg-[#C1F034]/20 text-[#C1F034] px-1.5 py-0.5 rounded border border-[#C1F034]/30">{notif.badge}</span>}
                        </div>
                        <p className="text-xs text-white/50 mt-1">{notif.desc}</p>
                      </div>
                      <div className={`w-10 h-5 rounded-full relative cursor-pointer border ${notif.defaultChecked ? 'bg-[#C1F034] border-[#C1F034]/20' : 'bg-white/10 border-white/10'}`}>
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

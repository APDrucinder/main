"use client";

import {
  Upload,
  ChevronRight,
  MapPin,
  Briefcase,
  DollarSign,
  Globe,
  Settings,
  FileText
} from "lucide-react";
import { useState } from "react";
import { ApiError } from "@/lib/api-client";
import { submitOnboarding } from "@/lib/api";

export default function OnboardingPage() {
  const [threshold, setThreshold] = useState(80);
  const [experienceRange, setExperienceRange] = useState("3-5");
  const [minSalary, setMinSalary] = useState("110000");
  const [remoteOk, setRemoteOk] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);

  async function handleSubmitOnboarding() {
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(null);
    try {
      await submitOnboarding({
        targetRoles: ["Web Designer", "UX/UI Designer"],
        preferredLocations: ["Los Angeles, CA"],
        experienceRange,
        minSalary: Number(minSalary.replace(/[^0-9]/g, "")) || 0,
        remoteOk,
        autoApplyThreshold: threshold,
      });
      setSaveSuccess("Onboarding preferences saved.");
    } catch (error) {
      setSaveError(error instanceof ApiError ? error.message : "Unable to save onboarding settings.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="w-full max-w-[1200px] mx-auto animate-in fade-in duration-700 font-sans mt-8 pb-20 text-white">

      <div className="mb-12">
        <h1 className="text-4xl font-light tracking-tight leading-tight mb-2 uppercase">
          AGENT <span className="font-bold">ONBOARDING</span>
        </h1>
        <p className="text-white/50">Configure your AI agent&apos;s parameters to start matching and applying to jobs.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">

        {/* Left Column: Form */}
        <div className="lg:col-span-8 space-y-6">

          {/* Resume Upload */}
          <div className="orion-card p-6 border border-[#C1F034]/20">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <FileText className="w-5 h-5 text-[#C1F034]" /> Resume
            </h2>
            <div className="w-full border-2 border-dashed border-white/10 rounded-2xl p-10 flex flex-col items-center justify-center bg-white/5 hover:bg-white/10 transition-colors cursor-pointer group">
              <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <Upload className="w-8 h-8 text-white/50" />
              </div>
              <p className="font-medium">Click to upload or drag and drop</p>
              <p className="text-xs text-white/40 mt-2">PDF, DOCX up to 10MB</p>
            </div>
          </div>

          {/* Core Preferences */}
          <div className="orion-card p-6">
            <h2 className="text-lg font-semibold mb-6 flex items-center gap-2">
              <Briefcase className="w-5 h-5 text-[#C1F034]" /> Target Preferences
            </h2>

            <div className="space-y-6">
              <div>
                <label className="text-xs font-medium text-white/60 uppercase mb-2 block">Target Roles (Multiple)</label>
                <div className="flex flex-wrap gap-2 mb-3">
                  <span className="glass-pill-active px-3 py-1 text-xs font-semibold flex items-center gap-1">Web Designer <span className="cursor-pointer">×</span></span>
                  <span className="glass-pill-active px-3 py-1 text-xs font-semibold flex items-center gap-1">UX/UI Designer <span className="cursor-pointer">×</span></span>
                  <span className="glass-pill px-3 py-1 text-xs font-semibold border-dashed">+ Add Role</span>
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-white/60 uppercase mb-2 block">Preferred Locations</label>
                <div className="flex flex-wrap gap-2 mb-3">
                  <span className="glass-pill-active px-3 py-1 text-xs font-semibold flex items-center gap-1"><MapPin className="w-3 h-3" /> Los Angeles, CA <span className="cursor-pointer">×</span></span>
                  <span className="glass-pill px-3 py-1 text-xs font-semibold border-dashed">+ Add Location</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-medium text-white/60 uppercase mb-2 block">Years of Experience</label>
                  <select value={experienceRange} onChange={(e) => setExperienceRange(e.target.value)} className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white outline-none focus:border-[#C1F034]/50 appearance-none">
                    <option value="1-3">1 - 3 Years</option>
                    <option value="3-5">3 - 5 Years</option>
                    <option value="5+">5+ Years</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-white/60 uppercase mb-2 block">Min Salary Expectation</label>
                  <div className="relative">
                    <DollarSign className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-white/40" />
                    <input type="text" value={minSalary} onChange={(e) => setMinSalary(e.target.value)} className="w-full bg-white/5 border border-white/10 rounded-xl pl-9 pr-4 py-3 text-sm text-white outline-none focus:border-[#C1F034]/50" />
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between p-4 bg-white/5 rounded-xl border border-white/10">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-white/10 flex items-center justify-center">
                    <Globe className="w-5 h-5 text-white/80" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-white">Remote OK</h3>
                    <p className="text-xs text-white/50">Agent will apply to remote positions globally</p>
                  </div>
                </div>
                {/* Custom Toggle */}
                <button type="button" onClick={() => setRemoteOk((prev) => !prev)} className={`w-12 h-6 rounded-full relative cursor-pointer border shadow-[0_0_15px_rgba(193,240,52,0.2)] ${remoteOk ? "bg-[#C1F034] border-[#C1F034]/20" : "bg-white/10 border-white/20"}`}>
                  <div className={`absolute top-1 w-4 h-4 bg-black rounded-full shadow-sm transition-all ${remoteOk ? "right-1" : "left-1"}`}></div>
                </button>
              </div>
            </div>
          </div>

        </div>

        {/* Right Column: Settings */}
        <div className="lg:col-span-4 space-y-6">

          {/* Threshold Slider */}
          <div className="orion-card p-6">
            <h2 className="text-lg font-semibold mb-6 flex items-center gap-2">
              <Settings className="w-5 h-5 text-[#C1F034]" /> Agent Settings
            </h2>

            <div className="mb-6">
              <div className="flex justify-between items-end mb-4">
                <label className="text-xs font-medium text-white/60 uppercase">Auto-Apply Threshold</label>
                <span className="text-xl font-bold text-[#C1F034]">{threshold}%</span>
              </div>
              <input
                type="range"
                min="50" max="90"
                value={threshold}
                onChange={(e) => setThreshold(parseInt(e.target.value))}
                className="w-full"
              />
              <p className="text-[10px] text-white/40 mt-3 text-center">
                Agent will only auto-apply if the match score is {threshold}% or higher.
              </p>
            </div>

            <div className="w-full h-px bg-white/10 my-6"></div>

            <button type="button" onClick={handleSubmitOnboarding} disabled={saving} className="w-full py-4 bg-[#C1F034] text-black font-bold rounded-xl hover:bg-[#A3E635] transition-colors flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(193,240,52,0.3)] disabled:cursor-not-allowed disabled:opacity-70">
              Save & Start Agent <ChevronRight className="w-4 h-4" />
            </button>
            {saveError ? <p className="mt-3 text-center text-xs text-red-300">{saveError}</p> : null}
            {saveSuccess ? <p className="mt-3 text-center text-xs text-[#C1F034]">{saveSuccess}</p> : null}
          </div>

          {/* Info Card */}
          <div className="orion-card p-6 border border-white/5 bg-transparent">
            <h3 className="text-sm font-semibold mb-2">How it works</h3>
            <ul className="text-xs text-white/50 space-y-3">
              <li className="flex gap-2"><span className="text-[#C1F034]">•</span> Your resume is parsed by our LLM to extract key skills and experiences.</li>
              <li className="flex gap-2"><span className="text-[#C1F034]">•</span> The Agent continuously scans job boards for matches.</li>
              <li className="flex gap-2"><span className="text-[#C1F034]">•</span> Applications are sent automatically if they meet your threshold.</li>
            </ul>
          </div>

        </div>

      </div>
    </div>
  );
}

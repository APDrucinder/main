"use client";

import {
  Upload,
  ChevronRight,
  MapPin,
  Briefcase,
  DollarSign,
  Globe,
  Settings,
  FileText,
  CheckCircle2,
  Loader2,
  X,
} from "lucide-react";
import { useState, useRef, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function OnboardingPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Resume state
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [resumeUploaded, setResumeUploaded] = useState(false);
  const [resumeUploading, setResumeUploading] = useState(false);
  const [existingResume, setExistingResume] = useState<string | null>(null);

  // Preferences state
  const [roles, setRoles] = useState<string[]>([]);
  const [newRole, setNewRole] = useState("");
  const [locations, setLocations] = useState<string[]>([]);
  const [newLocation, setNewLocation] = useState("");
  const [experienceYears, setExperienceYears] = useState(0);
  const [salaryMin, setSalaryMin] = useState(0);
  const [remoteOk, setRemoteOk] = useState(false);
  const [threshold, setThreshold] = useState(75);

  // Action state
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Load existing data
  useEffect(() => {
    const loadExisting = async () => {
      try {
        const [prefs, resume] = await Promise.all([
          api.getPreferences(),
          api.getResume().catch(() => null),
        ]);

        if (prefs) {
          setRoles(prefs.target_roles || []);
          setLocations(prefs.locations || []);
          setExperienceYears(prefs.experience_years || 0);
          setSalaryMin(prefs.salary_min || 0);
          setRemoteOk(prefs.remote_ok || false);
          setThreshold(prefs.auto_apply_threshold || 75);
        }

        if (resume && resume.file_url) {
          setExistingResume(resume.file_url);
          setResumeUploaded(true);
        }
      } catch {
        // First time — no existing data
      }
    };
    loadExisting();
  }, []);

  // Resume upload
  const handleFileSelect = useCallback(async (file: File) => {
    setResumeFile(file);
    setResumeUploading(true);
    try {
      await api.uploadResume(file);
      setResumeUploaded(true);
    } catch {
      // Upload failed
    } finally {
      setResumeUploading(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  }, [handleFileSelect]);

  // Tag management
  const addRole = () => {
    if (newRole.trim() && !roles.includes(newRole.trim())) {
      setRoles([...roles, newRole.trim()]);
      setNewRole("");
    }
  };

  const addLocation = () => {
    if (newLocation.trim() && !locations.includes(newLocation.trim())) {
      setLocations([...locations, newLocation.trim()]);
      setNewLocation("");
    }
  };

  // Save & Start
  const handleSaveAndStart = async () => {
    setSaving(true);
    try {
      await api.savePreferences({
        target_roles: roles,
        locations,
        experience_years: experienceYears,
        salary_min: salaryMin,
        remote_ok: remoteOk,
        auto_apply_threshold: threshold,
      });

      setSaved(true);

      // Start scan
      await api.runScan(locations.length > 0 ? locations : undefined);

      // Redirect to dashboard
      setTimeout(() => {
        router.push("/dashboard");
      }, 1500);
    } catch {
      setSaving(false);
    }
  };

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

            {resumeUploaded ? (
              <div className="flex items-center gap-4 p-6 bg-[#C1F034]/5 rounded-2xl border border-[#C1F034]/20">
                <CheckCircle2 className="w-8 h-8 text-[#C1F034]" />
                <div>
                  <p className="font-medium text-white">
                    {resumeFile ? resumeFile.name : "Resume uploaded"}
                  </p>
                  <p className="text-xs text-white/50 mt-1">
                    {resumeFile ? `${(resumeFile.size / 1024).toFixed(0)} KB` : "Previously uploaded"}
                  </p>
                </div>
                <button
                  onClick={() => { setResumeUploaded(false); setResumeFile(null); }}
                  className="ml-auto text-white/40 hover:text-white transition-colors"
                >
                  Replace
                </button>
              </div>
            ) : (
              <div
                onClick={() => fileInputRef.current?.click()}
                onDrop={handleDrop}
                onDragOver={e => e.preventDefault()}
                className="w-full border-2 border-dashed border-white/10 rounded-2xl p-10 flex flex-col items-center justify-center bg-white/5 hover:bg-white/10 transition-colors cursor-pointer group"
              >
                {resumeUploading ? (
                  <Loader2 className="w-8 h-8 animate-spin text-[#C1F034] mb-4" />
                ) : (
                  <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                    <Upload className="w-8 h-8 text-white/50" />
                  </div>
                )}
                <p className="font-medium">{resumeUploading ? "Uploading..." : "Click to upload or drag and drop"}</p>
                <p className="text-xs text-white/40 mt-2">PDF, DOCX up to 5MB</p>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.doc,.docx"
                  className="hidden"
                  onChange={e => {
                    const file = e.target.files?.[0];
                    if (file) handleFileSelect(file);
                  }}
                />
              </div>
            )}
          </div>

          {/* Core Preferences */}
          <div className="orion-card p-6">
            <h2 className="text-lg font-semibold mb-6 flex items-center gap-2">
              <Briefcase className="w-5 h-5 text-[#C1F034]" /> Target Preferences
            </h2>

            <div className="space-y-6">
              {/* Target Roles */}
              <div>
                <label className="text-xs font-medium text-white/60 uppercase mb-2 block">Target Roles</label>
                <div className="flex flex-wrap gap-2 mb-3">
                  {roles.map((role) => (
                    <span key={role} className="glass-pill-active px-3 py-1 text-xs font-semibold flex items-center gap-1">
                      {role}
                      <button onClick={() => setRoles(roles.filter(r => r !== role))} className="ml-1 hover:text-red-500">
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                  <div className="flex items-center gap-1">
                    <input
                      type="text"
                      value={newRole}
                      onChange={e => setNewRole(e.target.value)}
                      onKeyDown={e => e.key === "Enter" && addRole()}
                      placeholder="Add role..."
                      className="bg-transparent border-none outline-none text-xs text-white w-24"
                    />
                    <button onClick={addRole} className="glass-pill px-2 py-1 text-xs font-semibold border-dashed hover:bg-white/10">+</button>
                  </div>
                </div>
              </div>

              {/* Locations */}
              <div>
                <label className="text-xs font-medium text-white/60 uppercase mb-2 block">Preferred Locations</label>
                <div className="flex flex-wrap gap-2 mb-3">
                  {locations.map((loc) => (
                    <span key={loc} className="glass-pill-active px-3 py-1 text-xs font-semibold flex items-center gap-1">
                      <MapPin className="w-3 h-3" /> {loc}
                      <button onClick={() => setLocations(locations.filter(l => l !== loc))} className="ml-1 hover:text-red-500">
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                  <div className="flex items-center gap-1">
                    <input
                      type="text"
                      value={newLocation}
                      onChange={e => setNewLocation(e.target.value)}
                      onKeyDown={e => e.key === "Enter" && addLocation()}
                      placeholder="Add location..."
                      className="bg-transparent border-none outline-none text-xs text-white w-28"
                    />
                    <button onClick={addLocation} className="glass-pill px-2 py-1 text-xs font-semibold border-dashed hover:bg-white/10">+</button>
                  </div>
                </div>
              </div>

              {/* Experience & Salary */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-medium text-white/60 uppercase mb-2 block">Years of Experience</label>
                  <select
                    value={experienceYears}
                    onChange={e => setExperienceYears(parseInt(e.target.value))}
                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white outline-none focus:border-[#C1F034]/50 appearance-none"
                  >
                    <option value={0}>0 - 1 Years</option>
                    <option value={1}>1 - 3 Years</option>
                    <option value={3}>3 - 5 Years</option>
                    <option value={5}>5+ Years</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-white/60 uppercase mb-2 block">Min Salary (Annual)</label>
                  <div className="relative">
                    <DollarSign className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-white/40" />
                    <input
                      type="number"
                      value={salaryMin}
                      onChange={e => setSalaryMin(parseInt(e.target.value) || 0)}
                      className="w-full bg-white/5 border border-white/10 rounded-xl pl-9 pr-4 py-3 text-sm text-white outline-none focus:border-[#C1F034]/50"
                    />
                  </div>
                </div>
              </div>

              {/* Remote Toggle */}
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
                <button
                  onClick={() => setRemoteOk(!remoteOk)}
                  className={`w-12 h-6 rounded-full relative cursor-pointer border transition-colors ${
                    remoteOk
                      ? "bg-[#C1F034] border-[#C1F034]/20 shadow-[0_0_15px_rgba(193,240,52,0.2)]"
                      : "bg-white/10 border-white/10"
                  }`}
                >
                  <div className={`absolute top-1 w-4 h-4 bg-black rounded-full shadow-sm transition-all ${remoteOk ? "right-1" : "left-1"}`} />
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
                min="50" max="95"
                value={threshold}
                onChange={(e) => setThreshold(parseInt(e.target.value))}
                className="w-full"
              />
              <p className="text-[10px] text-white/40 mt-3 text-center">
                Agent will only auto-apply if the match score is {threshold}% or higher.
              </p>
            </div>

            <div className="w-full h-px bg-white/10 my-6" />

            <button
              onClick={handleSaveAndStart}
              disabled={saving || saved}
              className={`w-full py-4 font-bold rounded-xl flex items-center justify-center gap-2 transition-colors ${
                saved
                  ? "bg-[#C1F034]/20 text-[#C1F034] border border-[#C1F034]/30"
                  : "bg-[#C1F034] text-black hover:bg-[#A3E635] shadow-[0_0_20px_rgba(193,240,52,0.3)]"
              }`}
            >
              {saved ? (
                <>
                  <CheckCircle2 className="w-5 h-5" />
                  Saved! Redirecting...
                </>
              ) : saving ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  Save & Start Agent <ChevronRight className="w-4 h-4" />
                </>
              )}
            </button>
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

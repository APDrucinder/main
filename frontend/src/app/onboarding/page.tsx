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
  X
} from "lucide-react";
import { useRef, useState } from "react";
import { ApiError } from "@/lib/api-client";
import { submitOnboarding, uploadResume } from "@/lib/api";

export default function OnboardingPage() {
  const [targetRoles, setTargetRoles] = useState("");
  const [locations, setLocations] = useState("");
  const [threshold, setThreshold] = useState(80);
  const [experienceRange, setExperienceRange] = useState("0-1");
  const [minSalary, setMinSalary] = useState("");
  const [remoteOk, setRemoteOk] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);

  // Resume upload state
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  function handleFileSelect(file: File) {
    const allowed = ["application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"];
    if (!allowed.includes(file.type)) {
      setUploadError("Only PDF and Word files are accepted.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setUploadError("File too large. Maximum 5MB.");
      return;
    }
    setSelectedFile(file);
    setUploadError(null);
    setUploadSuccess(null);
  }

  async function handleUpload() {
    if (!selectedFile) return;
    setUploading(true);
    setUploadError(null);
    setUploadSuccess(null);
    try {
      const result = await uploadResume(selectedFile);
      setUploadSuccess(result.message || "Resume uploaded successfully!");
    } catch (error) {
      setUploadError(error instanceof ApiError ? error.message : "Failed to upload resume.");
    } finally {
      setUploading(false);
    }
  }

  async function handleSubmitOnboarding() {
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(null);
    try {
      await submitOnboarding({
        targetRoles: targetRoles.split(",").map((role) => role.trim()).filter(Boolean),
        preferredLocations: locations.split(",").map((location) => location.trim()).filter(Boolean),
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

            {uploadSuccess ? (
              <div className="w-full border-2 border-[#C1F034]/30 rounded-2xl p-10 flex flex-col items-center justify-center bg-[#C1F034]/5">
                <CheckCircle2 className="w-12 h-12 text-[#C1F034] mb-4" />
                <p className="font-medium text-[#C1F034]">{uploadSuccess}</p>
                <p className="text-xs text-white/40 mt-2">{selectedFile?.name}</p>
                <button
                  type="button"
                  onClick={() => { setSelectedFile(null); setUploadSuccess(null); }}
                  className="mt-4 text-xs text-white/50 hover:text-white underline"
                >
                  Upload a different file
                </button>
              </div>
            ) : selectedFile ? (
              <div className="w-full border-2 border-[#C1F034]/30 rounded-2xl p-8 flex flex-col items-center justify-center bg-white/5">
                <FileText className="w-12 h-12 text-[#C1F034] mb-3" />
                <p className="font-medium text-white">{selectedFile.name}</p>
                <p className="text-xs text-white/40 mt-1">{(selectedFile.size / 1024).toFixed(0)} KB</p>
                <div className="flex gap-3 mt-6">
                  <button
                    type="button"
                    onClick={handleUpload}
                    disabled={uploading}
                    className="px-6 py-2.5 bg-[#C1F034] text-black font-bold rounded-xl hover:bg-[#A3E635] transition-colors flex items-center gap-2 disabled:opacity-70 disabled:cursor-not-allowed shadow-[0_0_15px_rgba(193,240,52,0.2)]"
                  >
                    {uploading ? <><Loader2 className="w-4 h-4 animate-spin" /> Uploading...</> : <><Upload className="w-4 h-4" /> Upload Resume</>}
                  </button>
                  <button
                    type="button"
                    onClick={() => { setSelectedFile(null); setUploadError(null); }}
                    className="px-4 py-2.5 bg-white/5 border border-white/10 text-white/60 rounded-xl hover:bg-white/10 transition-colors flex items-center gap-2"
                  >
                    <X className="w-4 h-4" /> Remove
                  </button>
                </div>
                {uploadError && <p className="mt-3 text-xs text-red-300">{uploadError}</p>}
              </div>
            ) : (
              <div
                className={`w-full border-2 border-dashed rounded-2xl p-10 flex flex-col items-center justify-center transition-colors cursor-pointer group ${isDragging ? "border-[#C1F034] bg-[#C1F034]/10" : "border-white/10 bg-white/5 hover:bg-white/10"}`}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDragging(false);
                  const file = e.dataTransfer.files[0];
                  if (file) handleFileSelect(file);
                }}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.doc,.docx"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleFileSelect(file);
                  }}
                />
                <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  <Upload className="w-8 h-8 text-white/50" />
                </div>
                <p className="font-medium">Click to upload or drag and drop</p>
                <p className="text-xs text-white/40 mt-2">PDF, DOCX up to 5MB</p>
                {uploadError && <p className="mt-3 text-xs text-red-300">{uploadError}</p>}
              </div>
            )}
          </div>

          {/* Core Preferences */}
          <div className="orion-card p-6">
            <h2 className="text-lg font-semibold mb-6 flex items-center gap-2">
              <Briefcase className="w-5 h-5 text-[#C1F034]" /> Target Preferences
            </h2>

            <div className="space-y-6">
              <div>
                <label className="text-xs font-medium text-white/60 uppercase mb-2 block">Target Roles (Multiple)</label>
                <input
                  type="text"
                  value={targetRoles}
                  onChange={(e) => setTargetRoles(e.target.value)}
                  placeholder="Frontend Engineer, Product Designer"
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white outline-none placeholder:text-white/25 focus:border-[#C1F034]/50"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-white/60 uppercase mb-2 block">Preferred Locations</label>
                <div className="relative">
                  <MapPin className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-white/40" />
                  <input
                    type="text"
                    value={locations}
                    onChange={(e) => setLocations(e.target.value)}
                    placeholder="Remote, New York, Bengaluru"
                    className="w-full bg-white/5 border border-white/10 rounded-xl pl-9 pr-4 py-3 text-sm text-white outline-none placeholder:text-white/25 focus:border-[#C1F034]/50"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-medium text-white/60 uppercase mb-2 block">Years of Experience</label>
                  <select value={experienceRange} onChange={(e) => setExperienceRange(e.target.value)} className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white outline-none focus:border-[#C1F034]/50 appearance-none">
                    <option value="0-1">0 - 1 Years</option>
                    <option value="1-3">1 - 3 Years</option>
                    <option value="3-5">3 - 5 Years</option>
                    <option value="5+">5+ Years</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-white/60 uppercase mb-2 block">Min Salary Expectation</label>
                  <div className="relative">
                    <DollarSign className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-white/40" />
                    <input type="text" value={minSalary} onChange={(e) => setMinSalary(e.target.value)} placeholder="100000" className="w-full bg-white/5 border border-white/10 rounded-xl pl-9 pr-4 py-3 text-sm text-white outline-none placeholder:text-white/25 focus:border-[#C1F034]/50" />
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

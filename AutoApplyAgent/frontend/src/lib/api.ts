// /Users/sparshyadav/Developer/React-Projects/UI/src/lib/api.ts
import { apiRequest } from "@/lib/api-client";
import type {
  Application,
  DashboardResponse,
  DashboardJob,
  OnboardingPayload,
  SettingsPayload,
  User,
} from "@/lib/api-types";

type BackendUserEnvelope = {
  user: User;
};

type BackendDashboardResponse = {
  stats: {
    total_applied: number;
    applied_today: number;
    applied_this_week: number;
    interviews: number;
  };
  recent_applications: Array<{
    application_id: string;
    status: string;
    match_score: number | null;
    applied_at: string | null;
    job: {
      title: string;
      company: string;
      location: string | null;
      apply_url: string;
    };
  }>;
};

type BackendApplicationsResponse = {
  applications: Array<{
    application_id: string;
    status: string;
    match_score: number | null;
    applied_at: string | null;
    user_feedback: string | null;
    job: {
      title: string;
      company: string;
      salary_range: string | null;
      source: string | null;
    };
  }>;
  total: number;
};

function initials(company: string) {
  return company
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "?";
}

function formatDate(value: string | null) {
  if (!value) return "Unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function normalizeStatus(status: string) {
  const normalized = status.replace(/_/g, " ").toLowerCase();
  if (normalized === "applied") return "Applied";
  if (normalized === "matched") return "Matched";
  if (normalized === "failed") return "Failed";
  if (normalized === "manual required") return "Manual Required";
  if (normalized === "needs credentials") return "Needs Credentials";
  if (normalized === "below threshold") return "Below Threshold";
  return normalized.replace(/\b\w/g, (char) => char.toUpperCase());
}

function toDashboardJob(item: BackendDashboardResponse["recent_applications"][number]): DashboardJob {
  return {
    title: item.job.title,
    company: item.job.company,
    time: formatDate(item.applied_at),
    salary: "Not listed",
    type: "Full-time",
    level: "Open",
    location: item.job.location ?? "Remote",
    locationType: item.job.location?.toLowerCase().includes("remote") ? "Remote" : "On-site",
    applicants: normalizeStatus(item.status),
    match: item.match_score ?? 0,
    initial: initials(item.job.company),
  };
}

export async function login(email: string, password: string) {
  return apiRequest<Response>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
    rawResponse: true,
  });
}

export async function logout() {
  return apiRequest<null>("/auth/logout", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function me() {
  const response = await apiRequest<BackendUserEnvelope>("/auth/me");
  return response.user;
}

export async function meServer(cookieHeader: string) {
  const response = await apiRequest<BackendUserEnvelope>("/auth/me", {
    headers: {
      Cookie: cookieHeader,
    },
  });
  return response.user;
}

export async function getDashboard() {
  const response = await apiRequest<BackendDashboardResponse>("/dashboard");
  return {
    matched: response.stats.total_applied,
    matchedDelta: 0,
    applied: response.stats.applied_today,
    appliedDelta: response.stats.applied_this_week,
    interviews: response.stats.interviews,
    activeFeeds: response.recent_applications.length,
    activeFeedsDelta: 0,
    jobs: response.recent_applications.map(toDashboardJob),
  } satisfies DashboardResponse;
}

export async function getApplications() {
  const response = await apiRequest<BackendApplicationsResponse>("/applications");
  return response.applications.map((application) => ({
    id: application.application_id,
    company: application.job.company,
    role: application.job.title,
    score: application.match_score ?? 0,
    status: normalizeStatus(application.status),
    platform: application.job.source ?? "Unknown",
    date: formatDate(application.applied_at),
    feedback: application.user_feedback,
  })) satisfies Application[];
}

export async function updateSettings(payload: SettingsPayload) {
  return apiRequest<{ settings: unknown }>("/settings", {
    method: "PATCH",
    body: JSON.stringify({
      target_roles: payload.targetRoles.split(",").map((item) => item.trim()).filter(Boolean),
      locations: payload.locations.split(",").map((item) => item.trim()).filter(Boolean),
      experience_years: Number.parseInt(payload.experienceRange, 10) || 0,
      salary_min: Number(payload.minSalary.replace(/[^0-9]/g, "")) || 0,
      remote_ok: payload.remoteFlexibility,
      auto_apply_threshold: payload.autoApplyThreshold,
    }),
  });
}

export async function uploadResume(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return apiRequest<{ resume_id: string; file_url: string; status: string; message: string }>(
    "/resume/upload",
    {
      method: "POST",
      body: formData,
    }
  );
}

export async function submitOnboarding(payload: OnboardingPayload) {
  return apiRequest<{ onboarding_completed: boolean }>("/onboarding", {
    method: "POST",
    body: JSON.stringify({
      full_name: "Local User",
      target_roles: payload.targetRoles,
      locations: payload.preferredLocations,
      experience_years: Number.parseInt(payload.experienceRange, 10) || 0,
      salary_min: payload.minSalary,
      remote_ok: payload.remoteOk,
      auto_apply_threshold: payload.autoApplyThreshold,
    }),
  });
}

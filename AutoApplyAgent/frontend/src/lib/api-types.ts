// /Users/sparshyadav/Developer/React-Projects/UI/src/lib/api-types.ts
export interface User {
  id: string;
  email: string;
  name?: string;
  role?: string;
  subscription_tier?: string;
}

export interface DashboardJob {
  title: string;
  company: string;
  time: string;
  salary: string;
  type: string;
  level: string;
  location: string;
  locationType: string;
  applicants: string;
  match: number;
  initial: string;
  isTop?: boolean;
}

export interface DashboardResponse {
  matched: number;
  matchedDelta: number;
  applied: number;
  appliedDelta: number;
  interviews: number;
  activeFeeds: number;
  activeFeedsDelta: number;
  jobs: DashboardJob[];
}

export interface Application {
  id: string | number;
  company: string;
  role: string;
  score: number;
  status: string;
  platform: string;
  date: string;
  feedback: string | null;
}

export interface SettingsPayload {
  targetRoles: string;
  locations: string;
  experienceRange: string;
  minSalary: string;
  autoApplyThreshold: number;
  remoteFlexibility: boolean;
}

export interface OnboardingPayload {
  targetRoles: string[];
  preferredLocations: string[];
  experienceRange: string;
  minSalary: number;
  remoteOk: boolean;
  autoApplyThreshold: number;
}

export interface ScanStartResponse {
  scan_id: string;
  status: "running";
  message: string;
}

export interface ScanJobResult {
  title: string;
  company: string;
  location: string | null;
  score: number;
  reason: string;
  url: string;
  status: string | null;
}

export interface ScanRunResult {
  jobs_scraped: number;
  passed_filter?: number;
  total_scored?: number;
  above_threshold?: number;
  auto_applied?: number;
  jobs?: ScanJobResult[];
}

export interface ScanStatusResponse {
  scan_id: string;
  status: "running" | "completed" | "failed";
  step: string;
  result: ScanRunResult | null;
  error: string | null;
}

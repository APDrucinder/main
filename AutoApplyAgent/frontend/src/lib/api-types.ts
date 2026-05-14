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

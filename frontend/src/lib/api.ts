// /Users/sparshyadav/Developer/React-Projects/UI/src/lib/api.ts
import { apiRequest } from "@/lib/api-client";
import type {
  Application,
  DashboardResponse,
  OnboardingPayload,
  SettingsPayload,
  User,
} from "@/lib/api-types";

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
  return apiRequest<User>("/auth/me");
}

export async function meServer(cookieHeader: string) {
  return apiRequest<User>("/auth/me", {
    headers: {
      Cookie: cookieHeader,
    },
  });
}

export async function getDashboard() {
  return apiRequest<DashboardResponse>("/dashboard");
}

export async function getApplications() {
  return apiRequest<Application[]>("/applications");
}

export async function updateSettings(payload: SettingsPayload) {
  return apiRequest<SettingsPayload>("/settings", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function submitOnboarding(payload: OnboardingPayload) {
  return apiRequest<OnboardingPayload>("/onboarding", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

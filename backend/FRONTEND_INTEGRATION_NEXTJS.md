# Next.js Integration Guide (App Router)

This repo currently contains backend code only. Use these drop-in files in your Next.js app.

## 1) `.env.local`

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## 2) `src/lib/api-types.ts`

```ts
export interface User {
  id: string;
  email: string;
  subscription_tier: string;
}

export interface ApiError {
  code: string;
  message: string;
}

export interface Application {
  application_id: string;
  status: string;
  match_score: number | null;
  matched_skills: string[];
  missing_skills: string[];
  reasoning: string | null;
  manual_apply_url: string | null;
  applied_at: string | null;
  job: {
    id: string;
    title: string;
    company: string;
    location: string;
    salary_range: string | null;
    apply_url: string;
    source: string | null;
  };
}

export interface DashboardResponse {
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
      id: string;
      title: string;
      company: string;
      location: string;
      apply_url: string;
    };
  }>;
}

export interface SettingsPayload {
  target_roles: string[];
  locations: string[];
  experience_years: number;
  salary_min: number;
  remote_ok: boolean;
  auto_apply_threshold: number;
}

export interface OnboardingPayload extends SettingsPayload {
  full_name: string;
}
```

## 3) `src/lib/api-client.ts`

```ts
type ApiEnvelope<T> = { data: T };
type ErrorEnvelope = { error: { code: string; message: string } };

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiClientError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });

  const body = (await res.json()) as ApiEnvelope<T> | ErrorEnvelope;
  if (!res.ok) {
    const err = (body as ErrorEnvelope).error;
    throw new ApiClientError(
      err?.code ?? `HTTP_${res.status}`,
      err?.message ?? "Request failed",
      res.status
    );
  }
  return (body as ApiEnvelope<T>).data;
}
```

## 4) Server-side auth guard (layout/page)

```ts
import { redirect } from "next/navigation";
import { apiRequest } from "@/lib/api-client";

export async function requireSession() {
  try {
    const me = await apiRequest<{ user: { id: string } }>("/auth/me");
    return me.user;
  } catch {
    redirect("/login");
  }
}
```

## 5) Route wiring

- Login: `POST /auth/login`
- Logout: `POST /auth/logout`
- Me: `GET /auth/me`
- Dashboard: `GET /dashboard`
- Applications: `GET /applications`
- Settings submit: `PATCH /settings`
- Onboarding submit: `POST /onboarding`

Use `apiRequest(...)` for all of the above.

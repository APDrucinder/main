export class ApiError extends Error {
  code: string;
  status: number;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

type ErrorEnvelope = {
  error?: {
    code?: string;
    message?: string;
  };
};

type SuccessEnvelope<T> = {
  data: T;
};

type ApiRequestInit = RequestInit & {
  rawResponse?: boolean;
};

declare global {
  interface Window {
    Clerk?: {
      session?: {
        getToken: () => Promise<string | null>;
      } | null;
    };
  }
}

function getBaseUrl() {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL;
  if (!base) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL or NEXT_PUBLIC_API_URL is not configured.");
  }
  return base;
}

async function getClerkToken() {
  if (typeof window === "undefined") return null;
  try {
    // Right after sign-in, Clerk session can take a moment to hydrate.
    for (let attempt = 0; attempt < 5; attempt += 1) {
      const token = await window.Clerk?.session?.getToken();
      if (token) return token;
      await new Promise((resolve) => setTimeout(resolve, 120));
    }
    return null;
  } catch {
    return null;
  }
}

export async function apiRequest<T>(
  path: string,
  init?: ApiRequestInit
): Promise<T> {
  const baseUrl = getBaseUrl();
  const headers = new Headers(init?.headers);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);

  if (!headers.has("Content-Type") && init?.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  if (!headers.has("Authorization")) {
    const token = await getClerkToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, {
      ...init,
      headers,
      credentials: "include",
      cache: "no-store",
      signal: controller.signal,
    });
  } catch {
    clearTimeout(timeout);
    throw new ApiError("Backend is unreachable.", "BACKEND_UNREACHABLE", 503);
  }
  clearTimeout(timeout);

  if (init?.rawResponse) {
    return response as T;
  }

  if (!response.ok) {
    let payload: ErrorEnvelope | null = null;

    try {
      payload = (await response.json()) as ErrorEnvelope;
    } catch {
      payload = null;
    }

    throw new ApiError(
      payload?.error?.message ?? "Request failed.",
      payload?.error?.code ?? "REQUEST_FAILED",
      response.status
    );
  }

  const payload = (await response.json()) as SuccessEnvelope<T> | T;
  if (payload && typeof payload === "object" && "data" in payload) {
    return (payload as SuccessEnvelope<T>).data;
  }
  return payload as T;
}

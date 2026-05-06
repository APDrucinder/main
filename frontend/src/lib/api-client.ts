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
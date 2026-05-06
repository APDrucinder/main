const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
export const USER_ID = '858011cd-5a44-4e86-9bc7-0088c22b8efe'

function headers(json = false): Record<string, string> {
    const h: Record<string, string> = { 'X-User-Id': USER_ID }
    if (json) h['Content-Type'] = 'application/json'
    return h
}

async function request<T = any>(url: string, opts?: RequestInit): Promise<T> {
    const res = await fetch(url, opts)
    if (!res.ok) {
        const body = await res.text().catch(() => '')
        throw new Error(`API ${res.status}: ${body}`)
    }
    return res.json()
}

export const api = {

    // ── Scan (direct — no Celery) ─────────────────────────────
    runScan: (locations?: string[]) =>
        request(`${BASE_URL}/scan/run`, {
            method: 'POST',
            headers: headers(true),
            body: JSON.stringify({ locations }),
        }),

    getScanStatus: (scanId: string) =>
        request(`${BASE_URL}/scan/run/${scanId}/status`, {
            headers: headers(),
        }),

    // ── Resume ────────────────────────────────────────────────
    uploadResume: (file: File) => {
        const formData = new FormData()
        formData.append('file', file)
        return request(`${BASE_URL}/resume/upload?user_id=${USER_ID}`, {
            method: 'POST',
            headers: { 'X-User-Id': USER_ID },
            body: formData,
        })
    },

    getResume: () =>
        request(`${BASE_URL}/resume/${USER_ID}`, {
            headers: headers(),
        }),

    // ── Preferences ───────────────────────────────────────────
    savePreferences: (prefs: {
        target_roles: string[]
        locations: string[]
        experience_years: number
        salary_min: number
        remote_ok: boolean
        auto_apply_threshold: number
    }) =>
        request(`${BASE_URL}/preferences/${USER_ID}`, {
            method: 'POST',
            headers: headers(true),
            body: JSON.stringify(prefs),
        }),

    getPreferences: () =>
        request(`${BASE_URL}/preferences/${USER_ID}`, {
            headers: headers(),
        }).catch(() => null), // 404 = no prefs yet

    // ── Applications ──────────────────────────────────────────
    getApplications: () =>
        request<{ applications: any[]; total: number }>(
            `${BASE_URL}/applications/${USER_ID}`,
            { headers: headers() }
        ),

    getStats: () =>
        request<{
            applied_today: number
            applied_this_week: number
            total_applied: number
            interviews: number
            rejections: number
            response_rate_percent: number
        }>(`${BASE_URL}/applications/${USER_ID}/stats`, {
            headers: headers(),
        }),

    submitFeedback: (applicationId: string, feedback: 'got_interview' | 'rejected' | 'no_response') =>
        request(`${BASE_URL}/applications/${applicationId}/feedback`, {
            method: 'POST',
            headers: headers(true),
            body: JSON.stringify({ feedback }),
        }),
}
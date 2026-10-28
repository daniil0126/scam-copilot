export const API_URL = "http://localhost:8000"

export class ApiError extends Error {}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
    let res: Response
    try {
        res = await fetch(`${API_URL}${path}`, {
            ...init,
            headers: { "content-type": "application/json", ...init?.headers },
        })
    } catch {
        throw new ApiError("Cannot reach the Scam Copilot server. Is the backend running?")
    }
    if (!res.ok) {
        const body = await res.json().catch(() => null)
        const detail = typeof body?.detail === "string" ? body.detail : null
        throw new ApiError(res.status === 404 ? "This invoice was not found in PayPal." : (detail ?? `Server error (${res.status}).`))
    }
    return res.json() as Promise<T>
}

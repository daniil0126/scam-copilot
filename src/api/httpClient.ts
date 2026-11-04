import { API_URL, accessHeaders } from "./config.js"

export { API_URL }

export class ApiError extends Error {}

const INVOICE_NOT_FOUND = "This invoice was not found in PayPal."

// `notFound` replaces the message for a 404 on calls that are not about a PayPal invoice.
export async function request<T>(path: string, init?: RequestInit, notFound = INVOICE_NOT_FOUND): Promise<T> {
    let res: Response
    try {
        res = await fetch(`${API_URL}${path}`, {
            ...init,
            headers: { "content-type": "application/json", ...accessHeaders(), ...init?.headers },
        })
    } catch {
        throw new ApiError("Cannot reach the Scam Copilot server. Is the backend running?")
    }
    if (!res.ok) {
        const body = await res.json().catch(() => null)
        const detail = typeof body?.detail === "string" ? body.detail : null
        throw new ApiError(res.status === 404 ? notFound : (detail ?? `Server error (${res.status}).`))
    }
    return res.json() as Promise<T>
}

import { API_URL, ApiError, request } from "./httpClient.js"
import type { BulkCheckResponse, ChatTurn, HistoryEntry, InboundEmailResponse, MonitoringState, MonitoringStatus, VerificationResult } from "./types.js"

export const checkPayPalInvoice = (invoiceId: string) =>
    request<VerificationResult>("/checks", { method: "POST", body: JSON.stringify({ invoice_id: invoiceId }) })

// For invoices PayPal's API will not return (not ours): the backend reads the text of the payer page.
export const checkPayerPage = (url: string, text: string) =>
    request<VerificationResult>("/checks/page", { method: "POST", body: JSON.stringify({ url, text }) })

// Called from the side panel, not the content script: the backend's CORS allows only the extension's own origin.
const INBOUND_ERRORS: Record<number, string> = {
    503: "Email checks are turned off on the server (INBOUND_EMAIL_SECRET is not set).",
    401: "The inbound secret is wrong. Check it in Settings.",
    413: "This email is too large to check.",
}

export async function postInboundEmail(html: string, secret: string): Promise<InboundEmailResponse> {
    let res: Response
    try {
        res = await fetch(`${API_URL}/inbound/email`, {
            method: "POST",
            headers: { "content-type": "text/html", "x-inbound-secret": secret },
            body: html,
        })
    } catch {
        throw new ApiError("Cannot reach the Scam Copilot server. Is the backend running?")
    }
    if (!res.ok) {
        const body = await res.json().catch(() => null)
        const detail = typeof body?.detail === "string" ? body.detail : null
        throw new ApiError(res.status === 422 && detail ? detail : (INBOUND_ERRORS[res.status] ?? detail ?? `Server error (${res.status}).`))
    }
    return res.json() as Promise<InboundEmailResponse>
}

export const fetchHistory = () => request<HistoryEntry[]>("/checks")

export const checkAllPayPalInvoices = () => request<BulkCheckResponse>("/checks/bulk", { method: "POST" })

export const fetchAiStatus = () => request<{ enabled: boolean; provider: string | null }>("/ai/status")

// `checkId` makes the server add that stored check as context for the question.
export const sendChat = (messages: ChatTurn[], checkId?: string | null) =>
    request<{ reply: string }>("/chat", { method: "POST", body: JSON.stringify({ messages, check_id: checkId ?? null }) })

// Background monitoring: the backend polls PayPal on its own; these only read its state and control it.
export const fetchMonitoring = () => request<MonitoringStatus>("/monitoring")
export const pauseMonitoring = () => request<{ state: MonitoringState }>("/monitoring/pause", { method: "POST" })
export const resumeMonitoring = () => request<{ state: MonitoringState }>("/monitoring/resume", { method: "POST" })
export const syncMonitoring = () => request<{ jobId: string }>("/monitoring/sync", { method: "POST" })

import { API_URL, ApiError, request } from "./httpClient.js"
import type {
    AlertSettings, AppNotification, BulkCheckResponse, ChatEvent, ChatTurn, HistoryEntry, InboundEmailResponse, MonitoringState,
    MonitoringStatus, MonitoringSummary, MonthlyReport, NotificationsPage, VerificationResult,
} from "./types.js"

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

export const fetchAiStatus = () => request<{ enabled: boolean; provider: string | null; tools?: string[] }>("/ai/status")

// `checkId` makes the server add that stored check as context for the question.
export const sendChat = (messages: ChatTurn[], checkId?: string | null) =>
    request<{ reply: string; toolsUsed?: string[] }>("/chat", { method: "POST", body: JSON.stringify({ messages, check_id: checkId ?? null }) })

// The same answer as sendChat, but the steps of the assistant arrive while it works (one JSON object per line).
export async function sendChatStream(messages: ChatTurn[], checkId: string | null, onEvent: (event: ChatEvent) => void): Promise<void> {
    let res: Response
    try {
        res = await fetch(`${API_URL}/chat/stream`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ messages, check_id: checkId }),
        })
    } catch {
        throw new ApiError("Cannot reach the Scam Copilot server. Is the backend running?")
    }
    if (!res.ok || !res.body) {
        const body = await res.json().catch(() => null)
        throw new ApiError(typeof body?.detail === "string" ? body.detail : `Server error (${res.status}).`)
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffered = ""
    for (;;) {
        const { done, value } = await reader.read()
        buffered += decoder.decode(value, { stream: !done })
        const lines = buffered.split("\n")
        buffered = done ? "" : (lines.pop() ?? "")
        for (const line of lines) {
            if (line.trim()) onEvent(JSON.parse(line) as ChatEvent)
        }
        if (done) break
    }
}

// Background monitoring: the backend polls PayPal on its own; these only read its state and control it.
export const fetchMonitoring = () => request<MonitoringStatus>("/monitoring")
export const pauseMonitoring = () => request<{ state: MonitoringState }>("/monitoring/pause", { method: "POST" })
export const resumeMonitoring = () => request<{ state: MonitoringState }>("/monitoring/resume", { method: "POST" })
export const syncMonitoring = () => request<{ jobId: string }>("/monitoring/sync", { method: "POST" })

// Counters computed from the stored analyses (the monitor's own counters do not know duplicates or vendor anomalies yet).
export const fetchMonitoringSummary = () => request<MonitoringSummary>("/monitoring/summary")

// Alerts: one per stored invoice version at most, raised by the backend when a version is checked.
export const fetchNotifications = (opts: { unreadOnly?: boolean; cursor?: string | null; limit?: number } = {}) => {
    const query = new URLSearchParams()
    if (opts.unreadOnly) query.set("unreadOnly", "true")
    if (opts.cursor) query.set("cursor", opts.cursor)
    if (opts.limit) query.set("limit", String(opts.limit))
    const text = query.toString()
    return request<NotificationsPage>(`/notifications${text ? `?${text}` : ""}`)
}
export const fetchUnreadCount = () => request<{ unread: number }>("/notifications/unread-count")
export const markNotificationRead = (id: string) =>
    request<AppNotification>(`/notifications/${encodeURIComponent(id)}/read`, { method: "POST" }, "This alert no longer exists.")

export const fetchAlertSettings = () => request<AlertSettings>("/monitoring/settings")
export const saveAlertSettings = (settings: { alertThreshold: AlertSettings["alertThreshold"]; categories: Partial<AlertSettings["categories"]> }) =>
    request<AlertSettings>("/monitoring/settings", { method: "PUT", body: JSON.stringify(settings) })

// `month` is YYYY-MM. GET returns the last saved report or the same figures computed now; POST stores a new version.
export const fetchMonthlyReport = (month: string) => request<MonthlyReport>(`/reports/monthly?month=${encodeURIComponent(month)}`)
export const saveMonthlyReport = (month: string) =>
    request<MonthlyReport>("/reports/monthly", { method: "POST", body: JSON.stringify({ month }) })

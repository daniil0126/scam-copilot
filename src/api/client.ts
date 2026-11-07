import { accessHeaders } from "./config.js"
import { API_URL, ApiError, request } from "./httpClient.js"
import type {
    AlertSettings, AppNotification, BulkCheckResponse, ChatEvent, ChatTurn, HistoryEntry, InboundEmailResponse, MonitoringState,
    MonitoringStatus, MonitoringSummary, MonthlyReport, NotificationsPage, PayIntent, PayIntentStatus, PayTotals, PayView,
    VerificationResult,
} from "./types.js"

export const checkPayPalInvoice = (invoiceId: string) =>
    request<VerificationResult>("/checks", { method: "POST", body: JSON.stringify({ invoice_id: invoiceId }) })

// The AI explanation of a stored check. Slow (a model call), so it is asked for after the check is already on screen.
export const explainCheck = (checkId: string) =>
    request<VerificationResult>(`/checks/${encodeURIComponent(checkId)}/explain`, { method: "POST" }, "This check was not found.")

// For invoices PayPal's API will not return (not ours): the backend reads the text of the payer page.
export const checkPayerPage = (url: string, text: string) =>
    request<VerificationResult>("/checks/page", { method: "POST", body: JSON.stringify({ url, text }) })

// Called from the side panel, not the content script: the backend's CORS allows only the extension's own origin.
const INBOUND_ERRORS: Record<number, string> = {
    503: "Email checks are off on the server (PROJECT_ID is not set there).",
    401: "The server did not accept this extension for email checks. Check that PROJECT_ID on the server is this extension's ID, or the inbound secret in Settings.",
    413: "This email is too large to check.",
}

export async function postInboundEmail(html: string, secret: string): Promise<InboundEmailResponse> {
    let res: Response
    try {
        res = await fetch(`${API_URL}/inbound/email`, {
            method: "POST",
            headers: { "content-type": "text/html", ...(secret ? { "x-inbound-secret": secret } : {}), ...accessHeaders() },
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
            headers: { "content-type": "application/json", ...accessHeaders() },
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

// --- Paying. These calls only ask the server; no money moves here (backend/app/payments.py). ---

// A header a web page cannot add without a preflight: the server refuses state-changing payment calls without it.
const UI = { "x-requested-by": "scamcopilot-ui" }

export const previewPayments = (invoiceIds: string[]) =>
    request<{ items: PayView[]; totals: PayTotals }>("/payments/preview", { method: "POST", body: JSON.stringify({ invoiceIds }) })

export const checkInvoiceNow = (invoiceId: string) =>
    request<PayView>("/payments/check", { method: "POST", headers: UI, body: JSON.stringify({ invoiceId }) })

export type IntentsResult =
    | { ok: true; intents: PayIntent[]; totals: PayTotals }
    // The server found the basket no longer matches what the person reviewed: it sends the current state to review again.
    | { ok: false; message: string; items: PayView[]; totals: PayTotals }

export async function createPayIntents(
    invoiceIds: string[], source: "ui" | "chat", expectedTotals: PayTotals,
): Promise<IntentsResult> {
    let res: Response
    try {
        res = await fetch(`${API_URL}/payments/intents`, {
            method: "POST",
            headers: { "content-type": "application/json", ...accessHeaders(), ...UI },
            body: JSON.stringify({ invoiceIds, source, expectedIds: invoiceIds, expectedTotals }),
        })
    } catch {
        throw new ApiError("Cannot reach the Scam Copilot server. Is the backend running?")
    }
    const body = (await res.json().catch(() => null)) as {
        detail?: unknown; error?: { message?: string }; items?: PayView[]; intents?: PayIntent[]; totals?: PayTotals
    } | null
    if (res.status === 409 && Array.isArray(body?.items)) {
        return { ok: false, message: body.error?.message ?? "Review the list again.", items: body.items, totals: body.totals ?? {} }
    }
    if (!res.ok || !body?.intents) throw new ApiError(typeof body?.detail === "string" ? body.detail : `Server error (${res.status}).`)
    return { ok: true, intents: body.intents, totals: body.totals ?? {} }
}

export const markPayIntentOpened = (intentId: string) =>
    request<{ status: PayIntentStatus }>(`/payments/intents/${encodeURIComponent(intentId)}/opened`, { method: "POST", headers: UI }, "This payment is no longer known.")

export const cancelPayIntent = (intentId: string) =>
    request<{ status: PayIntentStatus }>(`/payments/intents/${encodeURIComponent(intentId)}/cancel`, { method: "POST", headers: UI }, "This payment is no longer known.")

export const fetchPayIntentStatus = (intentIds: string[]) =>
    request<{ items: { intentId: string; invoiceId: string; status: PayIntentStatus }[] }>(`/payments/intents?ids=${encodeURIComponent(intentIds.join(","))}`)

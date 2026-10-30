import { request } from "./httpClient.js"
import type { BulkCheckResponse, ChatTurn, HistoryEntry, MonitoringState, MonitoringStatus, VerificationResult } from "./types.js"

export const checkPayPalInvoice = (invoiceId: string) =>
    request<VerificationResult>("/checks", { method: "POST", body: JSON.stringify({ invoice_id: invoiceId }) })

// For invoices PayPal's API will not return (not ours): the backend reads the text of the payer page.
export const checkPayerPage = (url: string, text: string) =>
    request<VerificationResult>("/checks/page", { method: "POST", body: JSON.stringify({ url, text }) })

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

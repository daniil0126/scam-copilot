import { request } from "./httpClient.js"
import type { BulkCheckResponse, ChatTurn, HistoryEntry, VerificationResult } from "./types.js"

export const checkPayPalInvoice = (invoiceId: string) =>
    request<VerificationResult>("/checks", { method: "POST", body: JSON.stringify({ invoice_id: invoiceId }) })

export const fetchHistory = () => request<HistoryEntry[]>("/checks")

export const checkAllPayPalInvoices = () => request<BulkCheckResponse>("/checks/bulk", { method: "POST" })

export const fetchAiStatus = () => request<{ enabled: boolean; provider: string | null }>("/ai/status")

// `checkId` makes the server add that stored check as context for the question.
export const sendChat = (messages: ChatTurn[], checkId?: string | null) =>
    request<{ reply: string }>("/chat", { method: "POST", body: JSON.stringify({ messages, check_id: checkId ?? null }) })

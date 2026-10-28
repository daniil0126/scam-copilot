import { request } from "./httpClient.js"
import type { HistoryEntry, VerificationResult } from "./types.js"

export const checkPayPalInvoice = (invoiceId: string) =>
    request<VerificationResult>("/checks", { method: "POST", body: JSON.stringify({ invoice_id: invoiceId }) })

export const fetchHistory = () => request<HistoryEntry[]>("/checks")

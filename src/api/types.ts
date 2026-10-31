export type ExtensionMessage =
    | { action: "GET_DOM_STRUCTURE" }
    | { action: "GET_PAYPAL_INVOICE" }
    | { action: "GET_PAYPAL_EMAIL" }

export type PayPalInvoiceResponse = {
    invoiceId: string | null
    url: string
    // Visible text of the page, sent only because the user pressed the button. The backend caps it at 20 000 characters.
    text: string
}

export type PayPalEmailResponse = {
    // HTML of the PayPal invoice email found on the page, or null when there is none. Sent only because the user pressed the button.
    html: string | null
    // Set when reading the page failed inside the content script.
    error?: string
}

export type DOMResonse = {
    dom: string
    url: string
}

export type Message = {
    id: number
    role: "user" | "system"
    message: string
}

export type TabId = "check" | "monitor" | "history" | "chat" | "settings"

export type Theme = "light" | "dark"

export type UserSettings = {
    theme: Theme
    notifications: boolean
    width: number
    collapsed: boolean
}

export type RiskLevel = "low" | "medium" | "high"

export type FindingSeverity = RiskLevel | "ok"

export type Finding = {
    id: string
    label: string
    severity: FindingSeverity
    // Why the finding was raised, in one sentence. Absent on older stored results.
    detail?: string
    // The check could not run (for example nothing to compare with): neither a pass nor a risk.
    skipped?: boolean
}

export type ComparisonRow = {
    field: string
    current: string
    previous: string
    differs: boolean
}

export type Supplier = {
    name: string
    iban?: string
    email?: string
    phone?: string
}

export type Invoice = {
    number: string
    supplier: Supplier
    amount: number
    currency: string
    dueDate: string
    note?: string
    status?: string
}

export type VerificationResult = {
    id: string
    level: RiskLevel
    score: number
    invoice: Invoice
    checkedAt: string
    findings: Finding[]
    comparison: ComparisonRow[]
    recommendation: string
    evidence: string[]
    // Present only when the server has an LLM configured and it answered.
    ai?: { summary: string; provider: string }
}

export type HistoryEntry = VerificationResult

export type BulkCheckResponse = {
    results: VerificationResult[]
    errors: { invoiceId: string; error: string }[]
    summary: Record<RiskLevel, number> & { total: number; failed: number }
    truncated: boolean
}

export type ChatTurn = { role: "user" | "assistant"; content: string }

export type MonitoringState = "ACTIVE" | "PAUSED" | "ERROR"

// One stored version of an invoice that the background monitor picked up (GET /monitoring, `recentEvents`).
export type MonitoringEvent = {
    invoiceId: string
    eventType: "NEW_INVOICE" | "INVOICE_UPDATED"
    detectedAt: string
    invoiceNumber: string | null
    senderName: string | null
    amount: string | null
    currency: string | null
    status: string | null
    riskLevel: RiskLevel | null
    signals: string[]
}

export type MonitoringStatus = {
    state: MonitoringState
    lastSuccessfulSyncAt: string | null
    totalInvoices: number
    highRisk: number
    criticalRisk: number
    potentialDuplicates: number
    vendorAnomalies: number
    recentEvents: MonitoringEvent[]
    errors: string[]
}

export type InboundEmailKind = "new" | "updated" | "unknown"

// Answer of POST /inbound/email. `check` is null only for a duplicate whose first check was never stored.
export type InboundEmailResponse = {
    stored: boolean
    duplicate: boolean
    kind: InboundEmailKind
    template: string | null
    invoiceId: string
    invoice: Record<string, unknown>
    links: { url: string; text: string; host: string | null; isPaypal: boolean; textMismatch: boolean }[]
    check: VerificationResult | null
}

// What a result on screen was checked from. It decides which fields exist, so it is always shown with the result.
export type CheckSource = {
    kind: "api" | "page" | "email"
    label: string
    // What this source cannot show, so a missing field is not read as "fine" or as "changed".
    limits?: string
}

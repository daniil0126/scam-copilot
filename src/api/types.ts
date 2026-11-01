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

// One step of the assistant while it answers: a turn of the model or a PayPal read. Real events, not the model's reasoning.
export type TraceStep = {
    id: string
    kind: "model" | "tool" | "note"
    label: string
    detail?: string
    state: "running" | "done" | "failed"
}

// An invoice named in an answer, described by the server from PayPal's data and the checks it has stored.
export type InvoiceRef = {
    id: string
    number?: string
    status?: string
    amount?: string
    currency?: string
    created?: string
    payerPage?: string
    checkId?: string
    supplier?: string
    level?: RiskLevel
}

export type InvoiceTable = { rows: InvoiceRef[]; matched: number }

export type ChatEvent =
    | { type: "model"; id: string; state: TraceStep["state"]; first: boolean }
    | { type: "tool"; id: string; name: string; local?: boolean; args: Record<string, string | number | boolean>; state: TraceStep["state"]; summary?: string | null; reason?: string | null }
    | { type: "fallback" }
    | { type: "answer"; reply: string; toolsUsed: string[]; invoices?: InvoiceRef[]; table?: InvoiceTable | null }
    | { type: "error"; message: string }

export type Message = {
    id: number
    role: "user" | "system"
    message: string
    tools?: string[]  // PayPal reads the assistant made to answer, shown under its reply
    trace?: TraceStep[]  // the steps it took, shown folded under the reply
    invoices?: InvoiceRef[]  // invoices the reply names, so their ids can be shown as readable links
    table?: InvoiceTable  // the list the assistant was asked for, drawn from the server's data instead of written by the model
}

export type TabId = "check" | "monitor" | "history" | "chat" | "settings"

export type MonitorSection = "overview" | "alerts" | "report"

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

// Alerts, alert rules, the monthly report and the summary. The backend writes risk levels in capitals
// and has four of them, unlike the three lower-case `RiskLevel` of a single check.
export type AlertLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"

export type AlertEventType = "CRITICAL_RISK" | "HIGH_RISK" | "VENDOR_IMPERSONATION" | "POTENTIAL_DUPLICATE" | "SUSPICIOUS_PAYMENT_LINK"

// What an alert is about, from the invoice's latest stored check. Null when that check no longer exists.
export type AlertInvoice = {
    checkId: string
    number: string | null
    supplierName: string | null
    amount: number | null
    currency: string | null
    dueDate: string | null
}

export type AppNotification = {
    id: string
    invoiceId: string
    eventType: AlertEventType
    riskLevel: AlertLevel
    detectedAt: string
    signals: string[]
    read: boolean
    link: string
    title: string
    message: string
    invoice: AlertInvoice | null
}

export type NotificationsPage = {
    items: AppNotification[]
    unread: number
    nextCursor: string | null
}

export type AlertSettings = {
    alertThreshold: "HIGH" | "CRITICAL"
    categories: Record<AlertEventType, boolean>
}

export type MonitoringSummary = {
    invoices: number
    high: number
    critical: number
    potentialDuplicates: number
    vendorAnomalies: number
    recentDetections: { invoiceId: string; riskLevel: AlertLevel; detectedAt: string }[]
}

export type ReportMeta = { saved: boolean; version?: number; createdAt?: string }

export type EmptyReport = ReportMeta & { month: string; empty: true; message: string; wording: string }

export type FullReport = ReportMeta & {
    month: string
    empty: false
    wording: string
    analyses: number
    invoices: number
    byLevel: Record<AlertLevel, number>
    potentialDuplicates: number
    vendorAnomalies: number
    suspiciousLinks: number
    topFlaggedSuppliers: { supplierEmail: string; supplierName: string | null; flaggedInvoices: number }[]
    weeklyTrend: { weekStart: string; analyses: number; averageScore: number; highOrCritical: number }[]
    manualReview: {
        invoiceId: string
        riskLevel: AlertLevel
        riskScore: number
        supplierName: string | null
        signs: string[]
        // Absent in reports saved before these were added.
        number?: string | null
        amount?: number | null
        currency?: string | null
        dueDate?: string | null
        checkId?: string | null
    }[]
}

export type MonthlyReport = EmptyReport | FullReport

export type ExtensionMessage =
    | { action: "GET_DOM_STRUCTURE" }
    | { action: "GET_PAYPAL_INVOICE" }

export type PayPalInvoiceResponse = {
    invoiceId: string | null
    url: string
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

export type TabId = "check" | "history" | "chat" | "settings"

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
}

export type HistoryEntry = VerificationResult

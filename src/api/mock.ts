import type { HistoryEntry, Invoice, VerificationResult } from "./types.js"

export const DEMO_INVOICE: Invoice = {
    number: "#45872",
    supplier: { name: "Acme Supplies Ltd.", iban: "PL12 3456 7890 1234 5678 9012" },
    amount: 2480,
    currency: "USD",
    dueDate: "2025-11-15",
}

export const HIGH_RISK_RESULT: VerificationResult = {
    id: "check-high",
    level: "high",
    score: 86,
    invoice: DEMO_INVOICE,
    checkedAt: "2025-10-28T10:42:00",
    findings: [
        { id: "iban", label: "IBAN changed", severity: "high" },
        { id: "supplier", label: "New supplier", severity: "high" },
        { id: "amount", label: "Amount mismatch", severity: "medium" },
    ],
    comparison: [
        { field: "Supplier", current: "Acme Supplies Ltd.", previous: "Global Supplies Co.", differs: true },
        { field: "IBAN", current: "PL12 3456 7890 1234 5678 9012", previous: "PL98 7654 3210 9876 5432 1098", differs: true },
        { field: "Amount", current: "$2,480.00", previous: "$2,100.00", differs: true },
    ],
    recommendation: "This invoice differs from previous ones. We recommend contacting the supplier through an official channel.",
    evidence: [
        "The supplier name does not match any supplier in the check history.",
        "The bank account (IBAN) differs from the one used on the previous invoice.",
        "The total is $380.00 higher than the previous invoice.",
    ],
}

export const LOW_RISK_RESULT: VerificationResult = {
    id: "check-low",
    level: "low",
    score: 12,
    invoice: { ...DEMO_INVOICE, supplier: { name: "Global Tech Solutions", iban: "PL98 7654 3210 9876 5432 1098" }, amount: 1200 },
    checkedAt: "2025-10-27T15:10:00",
    findings: [
        { id: "supplier", label: "Supplier confirmed", severity: "ok" },
        { id: "iban", label: "IBAN matches", severity: "ok" },
        { id: "amount", label: "Amount within normal range", severity: "ok" },
    ],
    comparison: [],
    recommendation: "No obvious issues were found. Pay only through your usual, trusted channels.",
    evidence: [
        "The supplier name matches an earlier check.",
        "The IBAN is the same as on the previous invoice.",
        "The total is close to the usual amount for this supplier.",
    ],
}

const MEDIUM_RISK_RESULT: VerificationResult = {
    id: "check-medium",
    level: "medium",
    score: 48,
    invoice: { ...DEMO_INVOICE, amount: 2100 },
    checkedAt: "2025-10-24T09:05:00",
    findings: [{ id: "amount", label: "Amount differs from usual", severity: "medium" }],
    comparison: [{ field: "Amount", current: "$2,100.00", previous: "$1,650.00", differs: true }],
    recommendation: "The amount is unusual for this supplier. Confirm it with them before paying.",
    evidence: ["The total is higher than the previous invoice from this supplier."],
}

export const HISTORY: HistoryEntry[] = [
    { ...HIGH_RISK_RESULT, id: "h1" },
    { ...LOW_RISK_RESULT, id: "h2" },
    {
        ...LOW_RISK_RESULT,
        id: "h3",
        invoice: { ...LOW_RISK_RESULT.invoice, supplier: { name: "Bright Marketing Co.", iban: "PL55 1111 2222 3333 4444 5555" }, amount: 890 },
        checkedAt: "2025-10-26T11:30:00",
    },
    { ...MEDIUM_RISK_RESULT, id: "h4" },
]

export const ANALYSIS_STAGES = [
    "Extracting data",
    "Checking the supplier",
    "Analysing payment details",
    "Building the assessment",
]

export const DEMO_LINE_ITEMS = [
    { label: "Office supplies", amount: 2100 },
    { label: "Shipping", amount: 380 },
]

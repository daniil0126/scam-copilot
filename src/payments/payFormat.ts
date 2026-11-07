import type { PayTotals, PayView } from "../api/types.js"
import { money } from "../lib/money.js"

export const label = (v: Pick<PayView, "supplier" | "number">) =>
    [v.supplier ?? "Invoice", v.number ? `#${v.number}` : null].filter(Boolean).join(" ")

// One confirmation holds at most this many invoices (the server refuses more).
export const MAX_BASKET = 10

export const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`

// Sums per currency in whole cents and writes them the way the server does ("1240.00"), so the two can be compared exactly.
export function sumTotals(views: Pick<PayView, "amount" | "currency">[]): PayTotals {
    const cents: Record<string, number> = {}
    for (const v of views) {
        const value = Number(v.amount)
        if (v.currency && v.amount && Number.isFinite(value)) cents[v.currency] = (cents[v.currency] ?? 0) + Math.round(value * 100)
    }
    return Object.fromEntries(Object.keys(cents).sort().map(c => [c, (cents[c] / 100).toFixed(2)]))
}

// "$1,240.00 + €80.00": amounts in different currencies are listed, never added together.
export const totalsText = (totals: PayTotals) =>
    Object.entries(totals).map(([currency, amount]) => money(amount, currency) ?? `${amount} ${currency}`).join(" + ")

// Reasons that the row's own risk label does not already say, so they are written out under the row.
export const QUIET_REASONS = new Set(["risk_high", "risk_medium", "paid", "not_checked"])

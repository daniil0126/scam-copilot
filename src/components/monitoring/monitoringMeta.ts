import type { MonitoringEvent, MonitoringState } from "../../api/types.js"
import { formatMoney } from "../../lib/risk.js"

// Full class names only: Tailwind cannot detect names built from fragments.
export const STATE_META: Record<MonitoringState, { label: string; dot: string; pill: string }> = {
    ACTIVE: { label: "Live", dot: "bg-[var(--success)]", pill: "bg-[var(--success-soft)] text-[var(--success)]" },
    PAUSED: { label: "Paused", dot: "bg-[var(--muted)]", pill: "bg-[var(--border)] text-[var(--muted)]" },
    ERROR: { label: "Problem", dot: "bg-[var(--danger)]", pill: "bg-[var(--danger-soft)] text-[var(--danger)]" },
}

export const eventKey = (e: MonitoringEvent | undefined) => (e ? `${e.invoiceId}@${e.detectedAt}` : "")

export function money(amount: string | null, currency: string | null): string {
    const value = Number(amount)
    if (amount === null || Number.isNaN(value)) return "Amount unknown"
    try {
        return currency ? formatMoney(value, currency) : value.toFixed(2)
    } catch {
        return `${amount} ${currency ?? ""}`.trim()  // an unknown currency code
    }
}

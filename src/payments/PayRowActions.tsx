import { CheckCircle2, Loader2 } from "lucide-react"
import type { InvoiceRef } from "../api/types.js"
import { usePayments } from "./context.js"
import { QUIET_REASONS } from "./payFormat.js"

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"

// "3 min ago", from the time the server says the invoice was checked.
function ago(iso: string | null): string {
    if (!iso) return ""
    const minutes = Math.round((Date.now() - Date.parse(iso)) / 60000)
    if (!Number.isFinite(minutes) || minutes < 1) return "just now"
    if (minutes < 60) return `${minutes} min ago`
    const hours = Math.round(minutes / 60)
    return hours < 24 ? `${hours} h ago` : `${Math.round(hours / 24)} d ago`
}

// Under a row of the invoice table: the quiet Pay button for an invoice with no warning signs, or the way to get it checked.
// Rows that are risky say so already in their own risk label, so nothing is repeated here.
export default function PayRowActions({ invoice, title }: { invoice: InvoiceRef; title: string }) {
    const { views, review, checkNow, checking, inProgress, paid } = usePayments()
    const view = views[invoice.id]
    if (!view) return null

    if (paid.has(invoice.id) || inProgress.has(invoice.id)) {
        const done = paid.has(invoice.id)
        return (
            <p className={`flex items-center gap-1.5 pb-2.5 pl-[2.75rem] pr-3 text-[13px] ${done ? "text-[var(--success)]" : "text-[var(--primary)]"}`}>
                <CheckCircle2 size={14} aria-hidden />
                {done ? "Paid · confirmed by PayPal" : "Payment started on PayPal · not confirmed yet"}
            </p>
        )
    }

    if (view.eligible) {
        return (
            <div className="flex flex-wrap items-center justify-between gap-x-3 pb-1.5 pl-[2.75rem] pr-3">
                <span className="flex items-center gap-1.5 text-[13px] text-[var(--success)]">
                    <CheckCircle2 size={14} aria-hidden />
                    No warning signs{view.checkedAt ? ` · checked ${ago(view.checkedAt)}` : ""}
                </span>
                <button
                    onClick={e => review([invoice.id], "ui", e.currentTarget)}
                    aria-label={`Pay ${title}`}
                    className={`min-h-11 min-w-16 rounded-lg border border-[var(--primary)] px-3.5 text-sm font-semibold text-[var(--primary)] hover:bg-[var(--primary-soft)] ${FOCUS}`}
                >
                    Pay
                </button>
            </div>
        )
    }

    const code = view.reasons[0]?.code
    const canCheck = code === "not_checked" || code === "changed"
    const loud = view.reasons.filter(r => !QUIET_REASONS.has(r.code))
    if (!canCheck && loud.length === 0) return null
    const busy = checking.has(invoice.id)
    return (
        <div className="flex flex-wrap items-center justify-between gap-x-3 pb-1 pl-[2.75rem] pr-3 text-[13px]">
            <span className={code === "changed" ? "text-[var(--warning)]" : "text-[var(--muted)]"}>
                {code === "changed" ? "Changed since its check" : loud.map(r => r.text).join(" · ")}
            </span>
            {canCheck && (
                <button
                    onClick={() => { void checkNow(invoice.id) }}
                    disabled={busy}
                    aria-label={`Check ${title} now`}
                    className={`flex min-h-11 items-center gap-1.5 rounded-lg px-1.5 font-medium text-[var(--primary)] underline underline-offset-2 disabled:no-underline disabled:opacity-70 ${FOCUS}`}
                >
                    {busy ? <><Loader2 size={14} className="motion-safe:animate-spin" aria-hidden /> Checking…</> : "Check now"}
                </button>
            )}
        </div>
    )
}

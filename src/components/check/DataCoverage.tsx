import { Check, Minus } from "lucide-react"
import type { Invoice } from "../../api/types.js"

// What the check could actually see. A level means little without it: "low risk" on an invoice that shows no seller
// is not the same statement as "low risk" on a complete one, so what was missing is stated, not left to be noticed.
export default function DataCoverage({ invoice }: { invoice: Invoice }) {
    const fields = [
        { label: "Seller name", seen: Boolean(invoice.supplier.name?.trim()) },
        { label: "Seller email", seen: Boolean(invoice.supplier.email?.trim()) },
        { label: "Amount", seen: invoice.amount > 0 },
        { label: "Due date", seen: Boolean(invoice.dueDate) },
        { label: "Seller's note", seen: Boolean(invoice.note?.trim()) },
    ]
    const missing = fields.filter(f => !f.seen).length
    return (
        <section aria-label="What was read" className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
            <h3 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]">
                What was read{missing > 0 ? ` · ${missing} not shown` : ""}
            </h3>
            <ul className="flex flex-wrap gap-1.5">
                {fields.map(f => (
                    <li
                        key={f.label}
                        className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs ${f.seen ? "bg-[var(--success-soft)] text-[var(--success)]" : "bg-[var(--bg)] text-[var(--muted)] line-through decoration-[var(--muted)]/60"}`}
                    >
                        {f.seen ? <Check size={12} aria-hidden /> : <Minus size={12} aria-hidden />}
                        {f.label}
                        <span className="sr-only">{f.seen ? " read" : " not shown"}</span>
                    </li>
                ))}
            </ul>
            {missing > 0 && (
                <p className="mt-1.5 text-[11px] leading-snug text-[var(--muted)]">
                    Anything marked as not shown could not be checked. Missing details are not a sign of safety.
                </p>
            )}
        </section>
    )
}

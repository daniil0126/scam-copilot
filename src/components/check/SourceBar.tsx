import { Globe, Mail, Server, type LucideIcon } from "lucide-react"
import type { CheckSource, VerificationResult } from "../../api/types.js"

const ICONS: Record<CheckSource["kind"], LucideIcon> = { api: Server, page: Globe, email: Mail }

// Says what was checked and from what, above the verdict: the same invoice read from an email, a page or the API
// has different fields, and a reader must not take one for another.
export default function SourceBar({ source, result }: { source: CheckSource; result: VerificationResult }) {
    const Icon = ICONS[source.kind]
    const { number, supplier } = result.invoice
    return (
        <section aria-label="What was checked" className="mx-4 mt-4 rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
            <p className="flex items-center gap-2 text-xs font-semibold text-[var(--text)]">
                <Icon size={14} className="shrink-0 text-[var(--primary)]" aria-hidden />
                {source.label}
            </p>
            <p className="mt-1 text-sm font-medium text-[var(--text)]">
                {[number && `Invoice ${number}`, supplier.name].filter(Boolean).join(" · ") || "Invoice"}
            </p>
            {source.limits && <p className="mt-1 text-[11px] leading-snug text-[var(--muted)]">{source.limits}</p>}
        </section>
    )
}

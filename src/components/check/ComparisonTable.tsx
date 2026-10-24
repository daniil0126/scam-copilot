import { ArrowRight } from "lucide-react"
import type { ComparisonRow } from "../../types.js"

export default function ComparisonTable({ rows }: { rows: ComparisonRow[] }) {
    return (
        <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
            {rows.map(({ field, current, previous, differs }) => (
                <div key={field} className="border-b border-[var(--border)] px-3 py-2.5 last:border-b-0">
                    <div className="mb-1 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                        {field}
                        {differs && <span className="rounded bg-[var(--danger-soft)] px-1.5 py-0.5 text-[10px] text-[var(--danger)]">Differs</span>}
                    </div>
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm">
                        <span className={`break-all font-medium ${differs ? "text-[var(--danger)]" : "text-[var(--text)]"}`}>{current}</span>
                        <ArrowRight size={12} className="shrink-0 text-[var(--muted)]" aria-label="previously" />
                        <span className="break-all text-[var(--muted)]">{previous}</span>
                    </div>
                </div>
            ))}
        </div>
    )
}

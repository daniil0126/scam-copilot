import { ChevronRight } from "lucide-react"
import type { HistoryEntry } from "../../types.js"
import { LEVEL_META, formatDateTime, formatMoney } from "../../lib/risk.js"

export default function HistoryItem({ entry, onOpen }: { entry: HistoryEntry, onOpen: () => void }) {
    const meta = LEVEL_META[entry.level]
    const Icon = meta.icon
    const { supplier } = entry.invoice
    return (
        <li>
            <button
                onClick={onOpen}
                className="flex w-full items-center gap-3 border-b border-[var(--border)] px-4 py-3 text-left transition-colors hover:bg-[var(--primary-soft)] focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--primary)]"
            >
                <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${meta.soft} ${meta.text}`}>
                    <Icon size={18} aria-hidden />
                </span>
                <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold">{supplier.name}</span>
                    <span className="block text-xs text-[var(--muted)]">{formatDateTime(entry.checkedAt)}</span>
                </span>
                <span className="text-right">
                    <span className="block text-sm font-semibold">{formatMoney(entry.invoice.amount, entry.invoice.currency)}</span>
                    <span className={`block text-xs font-medium ${meta.text}`}>{meta.label}</span>
                </span>
                <ChevronRight size={16} className="shrink-0 text-[var(--muted)]" aria-hidden />
            </button>
        </li>
    )
}

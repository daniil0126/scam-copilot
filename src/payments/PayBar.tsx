import { usePayments } from "./context.js"
import { plural, sumTotals, totalsText } from "./payFormat.js"

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"

// Appears while invoices are ticked. The single main action of the screen is here; each row's own Pay is the quieter one.
export default function PayBar({ show }: { show: boolean }) {
    const { selection, views, clearSelection, review, sheet, queue, announce } = usePayments()
    const ids = [...selection].filter(id => views[id]?.eligible)
    return (
        <>
            <div role="status" aria-live="polite" className="sr-only">{announce}</div>
            {/* One thing at a time: while a payment is in progress its card is the only action at the bottom. */}
            {show && ids.length > 0 && !sheet && !queue && (
                <div className="flex shrink-0 flex-wrap items-center gap-2.5 border-t border-[var(--border)] bg-[var(--card)] px-4 py-2.5 shadow-[0_-6px_16px_rgba(23,41,75,.08)] motion-safe:animate-[sc-up_.18s_ease-out]">
                    <div className="min-w-[10rem] flex-1">
                        <b className="block text-sm tabular-nums [overflow-wrap:anywhere]">{totalsText(sumTotals(ids.map(id => views[id])))}</b>
                        <span className="text-[13px] text-[var(--muted)]">{plural(ids.length, "invoice")} selected</span>
                    </div>
                    <button onClick={clearSelection} className={`min-h-11 rounded-lg border border-[var(--border)] px-3.5 text-sm font-semibold hover:bg-[var(--primary-soft)] ${FOCUS}`}>Clear</button>
                    <button
                        onClick={e => review(ids, "ui", e.currentTarget)}
                        className={`min-h-11 rounded-lg border border-[var(--primary)] bg-[var(--primary)] px-3.5 text-sm font-semibold text-white hover:brightness-110 ${FOCUS}`}
                    >
                        Pay {plural(ids.length, "invoice")}
                    </button>
                </div>
            )}
        </>
    )
}

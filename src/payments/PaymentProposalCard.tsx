import { useState } from "react"
import { CheckCircle2 } from "lucide-react"
import type { PayProposal } from "../api/types.js"
import { money } from "../lib/money.js"
import { usePayments } from "./context.js"
import { MAX_BASKET, label, plural, sumTotals, totalsText } from "./payFormat.js"

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"

// What the assistant prepared. The invoices and the reasons for the ones left out come from the server's stored checks, not
// from the model's words. Nothing is paid from here: the button takes you to History with these invoices ticked, where the
// payment is reviewed and confirmed.
export default function PaymentProposalCard({ proposal, onReview }: { proposal: PayProposal; onReview?: (ids: string[]) => void }) {
    const { views, inProgress, paid } = usePayments()
    const [all, setAll] = useState(false)
    // Something may have been paid or changed since the answer was written: only what still has no warning signs is offered.
    const ready = proposal.items.filter(v => views[v.invoiceId]?.eligible !== false && !inProgress.has(v.invoiceId) && !paid.has(v.invoiceId))
    const started = proposal.items.length - ready.length
    const out = proposal.excluded
    const shown = all ? ready : ready.slice(0, 5)
    if (ready.length === 0 && out.length === 0) return <p className="mt-2 text-[13px] text-[var(--muted)]">Nothing is left to pay from this list.</p>
    return (
        <div className="mt-3 overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--bg)]">
            {ready.length > 0 && (
                <>
                    <p className="flex items-center gap-1.5 px-3 pt-2.5 text-sm font-semibold">
                        <CheckCircle2 size={16} className="text-[var(--success)]" aria-hidden />
                        {plural(ready.length, "invoice")} ready · <span className="tabular-nums">{totalsText(sumTotals(ready))}</span>
                    </p>
                    <ul className="px-3">
                        {shown.map(v => (
                            <li key={v.invoiceId} className="flex justify-between gap-2 border-t border-[var(--border)] py-1.5 text-[13px] first:mt-2">
                                <span className="min-w-0 [overflow-wrap:anywhere]">{label(v)}</span>
                                <span className="whitespace-nowrap tabular-nums">{money(v.amount ?? undefined, v.currency ?? undefined)}</span>
                            </li>
                        ))}
                    </ul>
                    {ready.length > 5 && (
                        <button onClick={() => setAll(a => !a)} aria-expanded={all} className={`min-h-11 px-3 text-[13px] font-medium text-[var(--primary)] ${FOCUS}`}>
                            {all ? "Show fewer" : `Show all ${ready.length}`}
                        </button>
                    )}
                    {ready.length > MAX_BASKET && (
                        <p className="px-3 pb-2 text-[13px] text-[var(--muted)]">One payment holds at most {MAX_BASKET} invoices, so you confirm them in batches.</p>
                    )}
                    {started > 0 && <p className="px-3 pb-2 text-[13px] text-[var(--muted)]">{plural(started, "invoice")} already started or paid and not listed.</p>}
                    <div className="border-t border-[var(--border)] p-3">
                        <button
                            onClick={() => onReview?.(ready.map(v => v.invoiceId))}
                            className={`min-h-11 w-full rounded-lg border border-[var(--primary)] bg-[var(--primary)] px-3.5 text-sm font-semibold text-white hover:brightness-110 ${FOCUS}`}
                        >
                            Review in History
                        </button>
                    </div>
                </>
            )}
            {out.length > 0 && (
                <details className="border-t border-[var(--border)] px-3 first:border-t-0">
                    <summary className={`flex min-h-11 cursor-pointer items-center text-[13px] text-[var(--muted)] ${FOCUS}`}>Left out ({out.length})</summary>
                    <ul className="pb-2">
                        {out.map(v => (
                            <li key={v.invoiceId} className="flex justify-between gap-2 py-1 text-[13px]">
                                <span className="min-w-0 [overflow-wrap:anywhere]">{label(v)}</span>
                                <span className="whitespace-nowrap text-[var(--muted)]">{v.reasons[0]?.text ?? "Cannot be paid"}</span>
                            </li>
                        ))}
                    </ul>
                </details>
            )}
        </div>
    )
}

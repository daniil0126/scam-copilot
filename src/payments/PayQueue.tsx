import { useState } from "react"
import { CheckCircle2, ChevronDown, Clock, ExternalLink, XCircle } from "lucide-react"
import { money } from "../lib/money.js"
import { usePayments, type QueueItem } from "./context.js"

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"

const STATE: Record<QueueItem["state"], { text: string; Icon: typeof Clock; tone: string }> = {
    ready: { text: "Not opened: your browser blocked the tab", Icon: Clock, tone: "text-[var(--warning)]" },
    opened: { text: "Opened on PayPal · not confirmed yet", Icon: ExternalLink, tone: "text-[var(--primary)]" },
    paid: { text: "Paid · confirmed by PayPal", Icon: CheckCircle2, tone: "text-[var(--success)]" },
    expired: { text: "Link expired, review the payment again", Icon: XCircle, tone: "text-[var(--warning)]" },
}

const PRIMARY = `min-h-11 rounded-lg border border-[var(--primary)] bg-[var(--primary)] px-4 text-sm font-semibold text-white hover:brightness-110 ${FOCUS}`
const SECONDARY = `min-h-11 rounded-lg border border-[var(--border)] px-4 text-sm font-semibold hover:bg-[var(--primary-soft)] ${FOCUS}`

// Payments in progress, kept small and at the bottom so the list stays in view. The pages of the chosen invoices are already open
// in their own tabs; this card only tracks them. "Paid" appears only after PayPal itself reports the invoice paid.
export default function PayQueue() {
    const { queue, openItem, dismissQueue } = usePayments()
    const [listOpen, setListOpen] = useState(false)
    if (!queue) return null

    const n = queue.length
    const paid = queue.filter(i => i.state === "paid").length
    const opened = queue.filter(i => i.state === "opened").length
    const blocked = queue.filter(i => i.state === "ready")
    const finished = blocked.length === 0 && opened === 0

    // The bar and the title say the same thing: how many are paid. It moves when PayPal reports an invoice paid.
    const title = finished ? (paid === n ? (n === 1 ? "Paid" : `All ${n} paid`) : `${paid} of ${n} paid`) : `${paid} of ${n} paid`
    const sub = finished ? "Confirmed by PayPal."
        : blocked.length ? `Your browser blocked ${blocked.length} tab${blocked.length === 1 ? "" : "s"}.`
        : `${opened} waiting for payment on PayPal`

    return (
        <section aria-label="Payment progress" className="shrink-0 border-t border-[var(--border)] bg-[var(--card)] px-4 pb-3 pt-3 shadow-[0_-6px_16px_rgba(23,41,75,.08)]">
            <div className="flex items-baseline justify-between gap-3">
                <h3 className="text-sm font-semibold">{title}</h3>
                <span className="text-right text-[13px] text-[var(--muted)]">{sub}</span>
            </div>
            {n > 1 && (
                <div role="progressbar" aria-label="Invoices paid" aria-valuemin={0} aria-valuemax={n} aria-valuenow={paid} className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--border)]">
                    <div className="h-full rounded-full bg-[var(--success)] transition-[width] motion-reduce:transition-none" style={{ width: `${(paid / n) * 100}%` }} />
                </div>
            )}
            <div className="mt-2 flex flex-wrap items-center gap-2">
                {blocked.length > 0 && <button onClick={() => { void openItem(blocked[0].intentId) }} className={PRIMARY}>Open on PayPal</button>}
                <button onClick={dismissQueue} className={SECONDARY}>{finished ? "Dismiss" : "Hide"}</button>
                {n > 1 && (
                    <button onClick={() => setListOpen(o => !o)} aria-expanded={listOpen} className={`ml-auto flex min-h-11 items-center gap-1 px-1 text-[13px] font-medium text-[var(--primary)] ${FOCUS}`}>
                        {listOpen ? "Hide list" : `Show all ${n}`}
                        <ChevronDown size={16} className={`transition-transform motion-reduce:transition-none ${listOpen ? "rotate-180" : ""}`} aria-hidden />
                    </button>
                )}
            </div>
            {(listOpen || n === 1) && (
                <ul className="mt-1 max-h-[48vh] divide-y divide-[var(--border)] overflow-y-auto border-t border-[var(--border)] motion-safe:animate-[sc-up_.18s_ease-out]">
                    {queue.map(item => {
                        const { text, Icon, tone } = STATE[item.state]
                        return (
                            <li key={item.intentId} className="flex items-start gap-2 py-2.5 text-sm">
                                <Icon size={16} className={`mt-0.5 shrink-0 ${tone}`} aria-hidden />
                                <span className="min-w-0 flex-1 [overflow-wrap:anywhere]">
                                    <b className="font-semibold">{item.title}</b>{item.amount && <span className="tabular-nums"> · {money(item.amount, item.currency ?? undefined)}</span>}
                                    <span className={`block ${tone}`}>{text}</span>
                                </span>
                                {(item.state === "opened" || item.state === "ready") && (
                                    <button onClick={() => { void openItem(item.intentId) }} aria-label={`Open ${item.title} on PayPal${item.state === "opened" ? " again" : ""}`} className={`min-h-11 shrink-0 px-1 text-[13px] font-medium text-[var(--primary)] underline underline-offset-2 ${FOCUS}`}>
                                        {item.state === "opened" ? "Open again" : "Open"}
                                    </button>
                                )}
                            </li>
                        )
                    })}
                </ul>
            )}
        </section>
    )
}

import { useState } from "react"
import { ExternalLink } from "lucide-react"
import type { InvoiceRef, InvoiceTable as Table } from "../../api/types.js"
import { LEVEL_META } from "../../lib/risk.js"
import { money } from "../../lib/money.js"

const PAGE = 20
const safePayerPage = (href?: string) => (href && /^https:\/\/www\.sandbox\.paypal\.com\//.test(href) ? href : null)
const capitalise = (word: string) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()

// Every row has the same three columns, so amounts and actions line up whether or not an invoice has a PayPal page.
const ROW = "grid grid-cols-[minmax(0,1fr)_2.75rem]"
const BUTTON = "grid grid-cols-[minmax(0,1fr)_6.5rem] items-center gap-x-3 border-l-[3px] py-2 pl-3 pr-1 text-left"

type Props = { table: Table; opening: string | null; onOpen: (invoice: InvoiceRef) => void; onPay?: () => void }

// The list the user asked for, drawn from the server's data (the model only writes the sentence above it). It runs the
// full width of the message, with no frame of its own. Risk is quiet by default: only medium and high get colour and a
// word; a low risk is announced to screen readers but not repeated on every row. A row opens the invoice's check in
// History, running the check first if there is none. Long lists show a page at a time.
export default function InvoiceTable({ table, opening, onOpen, onPay }: Props) {
    const [shown, setShown] = useState(PAGE)
    const rows = table.rows.slice(0, shown)
    if (table.rows.length === 0) {
        return <p className="mt-2 text-[13px] text-[var(--muted)]">No invoice matched.</p>
    }
    return (
        <div className="mt-3">
            <p className="mb-2 text-[13px] font-medium text-[var(--muted)]">
                {table.matched} {table.matched === 1 ? "invoice" : "invoices"}
                {table.matched > table.rows.length && ` · the first ${table.rows.length} are listed`}
            </p>
            <ul className="-mx-3.5 border-y border-[var(--border)]">
                {rows.map((invoice, index) => {
                    const level = invoice.level ? LEVEL_META[invoice.level] : null
                    const loud = invoice.level === "high" || invoice.level === "medium"
                    const page = safePayerPage(invoice.payerPage)
                    const amount = money(invoice.amount, invoice.currency)
                    const title = [invoice.supplier ?? "Invoice", invoice.number ? `#${invoice.number}` : null].filter(Boolean).join(" ")
                    return (
                        <li key={invoice.id} className={`${ROW} ${index > 0 ? "border-t border-[var(--border)]" : ""}`}>
                            <button
                                onClick={() => onOpen(invoice)}
                                disabled={opening === invoice.id}
                                aria-label={`${invoice.checkId ? "Open the check of" : "Check and open"} ${title}, ${amount ?? ""}${level ? `, ${level.label}` : ", not checked yet"}`}
                                style={{ borderLeftColor: loud && level ? level.stroke : "transparent" }}
                                className={`${BUTTON} min-h-[3.25rem] hover:bg-[var(--border)]/40 disabled:opacity-60 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--primary)]`}
                            >
                                <span className="min-w-0">
                                    <span className="block break-words text-sm font-medium leading-5 [overflow-wrap:anywhere]">
                                        {invoice.supplier ?? "Invoice"}
                                        {invoice.number && <span className="ml-1 font-normal tabular-nums text-[var(--muted)]">#{invoice.number}</span>}
                                    </span>
                                    <span className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[13px] leading-5 text-[var(--muted)]">
                                        <span className="tabular-nums">{invoice.created}</span>
                                        {invoice.status && (
                                            <span className="whitespace-nowrap rounded-md border border-[var(--border)] px-1.5 leading-[18px]">{capitalise(invoice.status)}</span>
                                        )}
                                    </span>
                                </span>
                                <span className="text-right">
                                    <span className="block whitespace-nowrap text-sm font-semibold tabular-nums leading-5">{amount}</span>
                                    {loud && level
                                        ? <span className={`block whitespace-nowrap text-[13px] font-medium leading-5 ${level.text}`}>{level.label}</span>
                                        : <span className="sr-only">{level ? level.label : "Not checked yet"}</span>}
                                    {!invoice.checkId && !loud && (
                                        <span className="block whitespace-nowrap text-[13px] leading-5 text-[var(--muted)]" aria-hidden>{opening === invoice.id ? "checking…" : "not checked"}</span>
                                    )}
                                </span>
                            </button>
                            {page ? (
                                <a
                                    href={page}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    aria-label={`Open ${title} on PayPal`}
                                    title="Open on PayPal"
                                    className="flex items-center justify-center text-[var(--primary)] hover:bg-[var(--border)]/40 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--primary)]"
                                >
                                    <ExternalLink size={16} aria-hidden />
                                </a>
                            ) : <span aria-hidden />}
                        </li>
                    )
                })}
            </ul>
            {shown < table.rows.length && (
                <button
                    onClick={() => setShown(n => n + PAGE)}
                    className="-mx-3.5 mt-0 flex min-h-11 w-[calc(100%+1.75rem)] items-center justify-center border-b border-[var(--border)] text-[13px] font-medium text-[var(--primary)] hover:bg-[var(--border)]/40 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--primary)]"
                >
                    Show {Math.min(PAGE, table.rows.length - shown)} more · {table.rows.length - shown} left
                </button>
            )}
            {onPay && table.rows.some(r => r.status === "SENT") && (
                <div className="-mx-3.5 flex items-center justify-between gap-3 px-3.5 pt-3">
                    <span className="text-[13px] text-[var(--muted)]">Paying is done in History, where the checks are.</span>
                    <button
                        onClick={onPay}
                        className="min-h-11 shrink-0 rounded-lg border border-[var(--primary)] px-3.5 text-sm font-semibold text-[var(--primary)] hover:bg-[var(--primary-soft)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"
                    >
                        Pay in History
                    </button>
                </div>
            )}
        </div>
    )
}

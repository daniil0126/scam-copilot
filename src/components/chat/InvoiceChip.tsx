import { ExternalLink } from "lucide-react"
import type { InvoiceRef } from "../../api/types.js"
import { LEVEL_META } from "../../lib/risk.js"
import { money } from "../../lib/money.js"

// A link to the PayPal payer page is shown only for the sandbox host the server builds it for.
const safePayerPage = (href?: string) => (href && /^https:\/\/www\.sandbox\.paypal\.com\//.test(href) ? href : null)

type Props = { invoice: InvoiceRef; busy: boolean; onOpen: (invoice: InvoiceRef) => void }

// An invoice id in an answer, written out: who, which number, how much, how risky. Pressing it opens its check in History
// (and runs the check first when there is none); the second link opens the invoice on PayPal's own page.
export default function InvoiceChip({ invoice, busy, onOpen }: Props) {
    const amount = money(invoice.amount, invoice.currency)
    const level = invoice.level ? LEVEL_META[invoice.level] : null
    const page = safePayerPage(invoice.payerPage)
    const what = [invoice.supplier ?? "Invoice", invoice.number ? `#${invoice.number}` : null, amount].filter(Boolean).join(" ")
    return (
        <span className="inline-flex max-w-full flex-wrap items-center gap-x-1.5 gap-y-1 align-middle">
            <button
                onClick={() => onOpen(invoice)}
                disabled={busy}
                aria-label={`${invoice.checkId ? "Open the check of" : "Check and open"} ${what}${level ? `, ${level.label}` : ""}`}
                title={invoice.id}
                className="inline-flex min-h-7 max-w-full items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-0.5 text-left text-[13px] font-medium text-[var(--text)] hover:border-[var(--primary)] disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-[var(--primary)]"
            >
                <span className="break-words [overflow-wrap:anywhere]">{what}</span>
                {level && <span className={`shrink-0 font-semibold ${level.text}`}>· {level.label}</span>}
                {!invoice.checkId && <span className="shrink-0 font-normal text-[var(--muted)]">· {busy ? "checking…" : "not checked yet"}</span>}
            </button>
            {page && (
                <a
                    href={page}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={`Open ${what} on PayPal`}
                    className="inline-flex min-h-7 items-center gap-1 rounded-lg px-1.5 text-[13px] font-medium text-[var(--primary)] hover:underline focus-visible:outline-2 focus-visible:outline-[var(--primary)]"
                >
                    PayPal <ExternalLink size={13} aria-hidden />
                </a>
            )}
        </span>
    )
}

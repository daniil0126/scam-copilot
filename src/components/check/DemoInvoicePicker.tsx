import { useEffect, useState } from "react"
import { Loader2, ScanSearch } from "lucide-react"
import { checkPayPalInvoice, fetchMonitoring } from "../../api/client.js"
import type { CheckSource, MonitoringEvent, VerificationResult } from "../../api/types.js"

type Props = {
    onResult: (result: VerificationResult, source: CheckSource) => void
}

const SOURCE: CheckSource = { kind: "api", label: "Checked from the PayPal account (API)" }
const EXTENSION_HELP = "https://github.com/daniil0126/scam-copilot#for-judges-try-it-in-3-minutes"

type Row = { id: string; supplier: string; amount: string; number: string | null }

// One row per invoice (the monitor lists a row per version), newest first. The risk level is left out on purpose: it is the answer.
function rowsOf(events: MonitoringEvent[]): Row[] {
    const seen = new Set<string>()
    const rows: Row[] = []
    for (const e of events) {
        if (seen.has(e.invoiceId)) continue
        seen.add(e.invoiceId)
        rows.push({
            id: e.invoiceId,
            supplier: e.senderName || "Unknown supplier",
            amount: e.amount ? `${e.amount} ${e.currency ?? ""}`.trim() : "",
            number: e.invoiceNumber,
        })
    }
    return rows
}

// The web copy cannot read a PayPal page (only the browser extension can), so it checks an invoice of the demo account by its id.
export default function DemoInvoicePicker({ onResult }: Props) {
    const [rows, setRows] = useState<Row[] | null>(null)
    const [busy, setBusy] = useState<string | null>(null)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        let alive = true
        fetchMonitoring()
            .then(status => { if (alive) setRows(rowsOf(status.recentEvents)) })
            .catch(e => { if (alive) { setRows([]); setError(e instanceof Error ? e.message : "Could not load the invoices.") } })
        return () => { alive = false }
    }, [])

    const run = async (id: string) => {
        setBusy(id)
        setError(null)
        try {
            onResult(await checkPayPalInvoice(id), SOURCE)
        } catch (e) {
            setError(e instanceof Error ? e.message : "Something went wrong.")
        } finally {
            setBusy(null)
        }
    }

    return (
        <section aria-label="Pick an invoice to check" className="border-b border-[var(--border)] p-4">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--text)]">
                <ScanSearch size={18} aria-hidden /> Pick an invoice to check
            </h2>
            <p className="mt-1 text-[11px] leading-snug text-[var(--muted)]">
                These are invoices of the Sandbox demo account. In the browser extension the same check reads the PayPal page you have open,
                so it also works on invoices from other senders.{" "}
                <a href={EXTENSION_HELP} target="_blank" rel="noreferrer" className="underline">Get the extension</a>
            </p>
            {rows === null && (
                <p className="mt-3 flex items-center gap-2 text-xs text-[var(--muted)]">
                    <Loader2 size={14} className="motion-safe:animate-spin" aria-hidden /> Loading the demo invoices (the first load can take a minute)...
                </p>
            )}
            <ul className="mt-3 space-y-2">
                {rows?.slice(0, 12).map(row => (
                    <li key={row.id}>
                        <button
                            onClick={() => void run(row.id)}
                            disabled={busy !== null}
                            className="flex w-full items-center justify-between gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2.5 text-left text-sm hover:border-[var(--primary)] active:scale-[0.99] disabled:opacity-70 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"
                        >
                            <span className="min-w-0">
                                <span className="block truncate font-medium text-[var(--text)]">{row.supplier}</span>
                                <span className="block text-[11px] text-[var(--muted)]">{row.number ? `Invoice ${row.number}` : "Invoice"}</span>
                            </span>
                            <span className="flex shrink-0 items-center gap-2 text-xs font-semibold text-[var(--text)]">
                                {row.amount}
                                {busy === row.id && <Loader2 size={14} className="motion-safe:animate-spin" aria-hidden />}
                            </span>
                        </button>
                    </li>
                ))}
            </ul>
            {rows?.length === 0 && !error && <p className="mt-3 text-xs text-[var(--muted)]">No invoices yet.</p>}
            {error && <p role="alert" className="mt-2 text-xs font-medium text-[var(--danger)]">{error}</p>}
        </section>
    )
}

import { useState } from "react"
import { Loader2, ScanSearch, Folder } from "lucide-react"
import { checkAllPayPalInvoices, checkPayPalInvoice } from "../../api/client.js"
import type { BulkCheckResponse, VerificationResult } from "../../api/types.js"
import { getPageInvoiceId } from "../../lib/pageInvoice.js"

type Props = {
    onResult: (result: VerificationResult) => void
    onOpenHistory: () => void
}

export default function PageCheckCard({ onResult, onOpenHistory }: Props) {
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [bulkBusy, setBulkBusy] = useState(false)
    const [bulkError, setBulkError] = useState<string | null>(null)
    const [bulk, setBulk] = useState<BulkCheckResponse | null>(null)

    const runAll = async () => {
        setBulkBusy(true)
        setBulkError(null)
        setBulk(null)
        try {
            setBulk(await checkAllPayPalInvoices())
        } catch (e) {
            setBulkError(e instanceof Error ? e.message : "Something went wrong.")
        } finally {
            setBulkBusy(false)
        }
    }

    const run = async () => {
        setBusy(true)
        setError(null)
        try {
            const invoiceId = await getPageInvoiceId()
            if (!invoiceId) {
                setError("No PayPal invoice found on this page. Open an invoice from PayPal and try again.")
                return
            }
            onResult(await checkPayPalInvoice(invoiceId))
        } catch (e) {
            setError(e instanceof Error ? e.message : "Something went wrong.")
        } finally {
            setBusy(false)
        }
    }

    return (
        <section aria-label="Check the current page" className="border-b border-[var(--border)] p-4">
            <button
                onClick={run}
                disabled={busy}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--primary)] px-4 py-3 text-sm font-semibold text-white hover:brightness-110 active:scale-[0.98] disabled:opacity-70 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"
            >
                {busy ? <Loader2 size={18} className="motion-safe:animate-spin" aria-hidden /> : <ScanSearch size={18} aria-hidden />}
                {busy ? "Checking the invoice..." : "Check this PayPal invoice"}
            </button>
            <button
                onClick={runAll}
                disabled={bulkBusy}
                className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--primary-soft)] px-4 py-3 text-sm font-semibold text-[var(--primary)] hover:brightness-90 active:scale-[0.98] disabled:opacity-70 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"
            >
                {bulkBusy ? <Loader2 size={18} className="motion-safe:animate-spin" aria-hidden /> : <Folder size={18} aria-hidden />}
                {bulkBusy ? "Checking all invoices..." : "Check all invoices"}
            </button>
            {bulk && (
                <div role="status" className="mt-2 rounded-xl border border-[var(--border)] p-3 text-xs">
                    <p className="font-semibold">
                        {bulk.summary.total === 0 ? "No invoices found in this PayPal account." : `Checked ${bulk.summary.total} invoices`}
                    </p>
                    {bulk.summary.total > 0 && (
                        <p className="mt-1 text-[var(--muted)]">
                            <span className="font-medium text-[var(--success)]">{bulk.summary.low} low</span>
                            {" · "}
                            <span className="font-medium text-[var(--warning)]">{bulk.summary.medium} medium</span>
                            {" · "}
                            <span className="font-medium text-[var(--danger)]">{bulk.summary.high} high</span>
                        </p>
                    )}
                    {bulk.summary.failed > 0 && (
                        <p className="mt-1 font-medium text-[var(--danger)]">{bulk.summary.failed} could not be checked.</p>
                    )}
                    {bulk.truncated && <p className="mt-1 text-[var(--muted)]">Only the first {bulk.summary.total + bulk.summary.failed} invoices were checked.</p>}
                    {bulk.summary.total > 0 && (
                        <button onClick={onOpenHistory} className="mt-2 font-semibold text-[var(--primary)] hover:underline focus-visible:outline-2 focus-visible:outline-[var(--primary)]">
                            Open History
                        </button>
                    )}
                </div>
            )}
            {bulkError && <p role="alert" className="mt-2 text-xs font-medium text-[var(--danger)]">{bulkError}</p>}
            <p className="mt-2 text-[11px] leading-snug text-[var(--muted)]">
                Reads the invoice number from the open PayPal page and checks it with PayPal. Nothing is read until you press the button.
            </p>
            {error && <p role="alert" className="mt-2 text-xs font-medium text-[var(--danger)]">{error}</p>}
        </section>
    )
}

import { useState } from "react"
import { Loader2, ScanSearch } from "lucide-react"
import { checkPayPalInvoice, checkPayerPage } from "../../api/client.js"
import type { VerificationResult } from "../../api/types.js"
import { getPageInvoice } from "../../lib/pageInvoice.js"

type Props = {
    onResult: (result: VerificationResult) => void
    onOpenHistory: () => void
}

// "Check all invoices" is hidden until the Batch Audit tab: /checks/bulk and checkAllPayPalInvoices stay for it.
export default function PageCheckCard({ onResult }: Props) {
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const run = async () => {
        setBusy(true)
        setError(null)
        try {
            const page = await getPageInvoice()
            if (!page?.invoiceId) {
                setError("No PayPal invoice found on this page. Open an invoice from PayPal and try again.")
                return
            }
            // The payer page is how a stranger's invoice is checked: PayPal's API only returns our own invoices.
            const isPayerPage = new URL(page.url).pathname.startsWith("/invoice/p/")
            onResult(isPayerPage ? await checkPayerPage(page.url, page.text) : await checkPayPalInvoice(page.invoiceId))
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
            <p className="mt-2 text-[11px] leading-snug text-[var(--muted)]">
                Reads the text of the open PayPal invoice page and checks it. Nothing is read until you press the button.
            </p>
            {error && <p role="alert" className="mt-2 text-xs font-medium text-[var(--danger)]">{error}</p>}
        </section>
    )
}

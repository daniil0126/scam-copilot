import { useState } from "react"
import { Loader2, Mail, ScanSearch } from "lucide-react"
import { checkPayPalInvoice, checkPayerPage, postInboundEmail } from "../../api/client.js"
import type { CheckSource, VerificationResult } from "../../api/types.js"
import { getPageInvoice } from "../../lib/pageInvoice.js"
import { getPageEmail } from "../../lib/paypalEmail.js"
import { loadInboundSecret } from "../../lib/inboundSecret.js"

type Props = {
    onResult: (result: VerificationResult, source: CheckSource) => void
    onOpenHistory: () => void
}

const API_SOURCE: CheckSource = { kind: "api", label: "Checked from your PayPal account (API)" }
const PAGE_SOURCE: CheckSource = {
    kind: "page",
    label: "Checked from the payer page",
    limits: "The page does not show the seller's phone, and not always their email.",
}
const EMAIL_LIMITS = "Based on the email only. PayPal emails do not show the seller's PayPal email or phone, and an update email does not show the seller's note, so those were not checked here."

// "Check all invoices" is hidden until the Batch Audit tab: /checks/bulk and checkAllPayPalInvoices stay for it.
export default function PageCheckCard({ onResult }: Props) {
    const [busy, setBusy] = useState<"invoice" | "email" | null>(null)
    const [error, setError] = useState<string | null>(null)

    const run = async () => {
        setBusy("invoice")
        setError(null)
        try {
            const page = await getPageInvoice()
            if (!page?.invoiceId) {
                setError("No PayPal invoice found on this page. Open an invoice from PayPal and try again.")
                return
            }
            // The payer page is how a stranger's invoice is checked: PayPal's API only returns our own invoices.
            const isPayerPage = new URL(page.url).pathname.startsWith("/invoice/p/")
            onResult(
                isPayerPage ? await checkPayerPage(page.url, page.text) : await checkPayPalInvoice(page.invoiceId),
                isPayerPage ? PAGE_SOURCE : API_SOURCE,
            )
        } catch (e) {
            setError(e instanceof Error ? e.message : "Something went wrong.")
        } finally {
            setBusy(null)
        }
    }

    const runEmail = async () => {
        setBusy("email")
        setError(null)
        try {
            const secret = await loadInboundSecret()  // optional: the server accepts the extension without one
            const { html, error: readError } = await getPageEmail()
            if (readError) {
                setError(`Could not read the email from this page: ${readError}`)
                return
            }
            if (!html) {
                setError("No PayPal invoice email found on this page. Open the email and try again.")
                return
            }
            const res = await postInboundEmail(html, secret)
            if (!res.check) {
                setError("This email was already checked, but its result is not stored.")
                return
            }
            onResult(res.check, {
                kind: "email",
                label: res.kind === "updated" ? "Checked from an updated-invoice email" : "Checked from an invoice email",
                limits: EMAIL_LIMITS,
            })
        } catch (e) {
            setError(e instanceof Error ? e.message : "Something went wrong.")
        } finally {
            setBusy(null)
        }
    }

    return (
        <section aria-label="Check the current page" className="border-b border-[var(--border)] p-4">
            <button
                onClick={run}
                disabled={busy !== null}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--primary)] px-4 py-3 text-sm font-semibold text-white hover:brightness-110 active:scale-[0.98] disabled:opacity-70 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"
            >
                {busy === "invoice" ? <Loader2 size={18} className="motion-safe:animate-spin" aria-hidden /> : <ScanSearch size={18} aria-hidden />}
                {busy === "invoice" ? "Checking the invoice..." : "Check this PayPal invoice"}
            </button>
            <button
                onClick={runEmail}
                disabled={busy !== null}
                className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl border border-[var(--primary)] px-4 py-3 text-sm font-semibold text-[var(--primary)] hover:bg-[var(--primary-soft)] active:scale-[0.98] disabled:opacity-70 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"
            >
                {busy === "email" ? <Loader2 size={18} className="motion-safe:animate-spin" aria-hidden /> : <Mail size={18} aria-hidden />}
                {busy === "email" ? "Checking the email..." : "Check this email"}
            </button>
            <p className="mt-2 text-[11px] leading-snug text-[var(--muted)]">
                Reads the open PayPal invoice page, or an open PayPal invoice email, and checks it. Nothing is read until you press a button.
            </p>
            {error && <p role="alert" className="mt-2 text-xs font-medium text-[var(--danger)]">{error}</p>}
        </section>
    )
}

import { useEffect, useRef, type KeyboardEvent } from "react"
import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react"
import { money } from "../lib/money.js"
import { usePayments } from "./context.js"
import { label, plural, sumTotals, totalsText } from "./payFormat.js"

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"

// The confirmation. It lists exactly what will be paid and says that the payment itself happens on PayPal's page. The
// server checks every invoice again when "Continue to PayPal" is pressed, so this list can be refused and shown again.
export default function PaySheet() {
    const { sheet, views, closeSheet, confirm, sheetOpener } = usePayments()
    const titleRef = useRef<HTMLHeadingElement>(null)
    const dialogRef = useRef<HTMLElement>(null)
    const open = sheet !== null

    useEffect(() => {
        if (!open) return
        titleRef.current?.focus()
        const opener = sheetOpener.current
        return () => { if (opener instanceof HTMLElement && opener.isConnected) opener.focus({ preventScroll: true }) }
    }, [open, sheetOpener])

    // A change of the list is announced and read from the top.
    const notice = sheet?.notice ?? null
    useEffect(() => { if (notice) titleRef.current?.focus() }, [notice])

    if (!sheet) return null
    const busy = sheet.phase === "paying"
    const loading = sheet.phase === "loading"
    const items = sheet.ids.map(id => views[id]).filter(Boolean)
    const totals = sumTotals(items)
    const limited = items.some(v => v.limited)

    const onKeyDown = (e: KeyboardEvent) => {
        if (e.key === "Escape") {
            e.stopPropagation()  // the panel itself closes on Escape; here it only closes this sheet
            if (!busy) closeSheet()
            return
        }
        if (e.key !== "Tab") return
        const focusable = [...(dialogRef.current?.querySelectorAll<HTMLElement>("button:not(:disabled), [tabindex='-1']") ?? [])]
        if (focusable.length === 0) return
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        const active = (dialogRef.current?.getRootNode() as Document | ShadowRoot).activeElement
        if (e.shiftKey && active === first) { e.preventDefault(); last.focus() }
        else if (!e.shiftKey && active === last) { e.preventDefault(); first.focus() }
    }

    return (
        <>
            <div aria-hidden className="absolute inset-0 z-30 bg-black/55 motion-safe:animate-[sc-fade_.15s_ease-out]" onClick={() => { if (!busy) closeSheet() }} />
            <section
                ref={dialogRef}
                role="dialog"
                aria-modal="true"
                aria-labelledby="pay-sheet-title"
                onKeyDown={onKeyDown}
                className="absolute inset-x-0 bottom-0 z-40 max-h-[92%] overflow-y-auto rounded-t-2xl border-t border-[var(--border)] bg-[var(--card)] px-4 pb-4 pt-4 shadow-2xl motion-safe:animate-[sc-up_.2s_ease-out]"
            >
                <h2 id="pay-sheet-title" ref={titleRef} tabIndex={-1} className="text-lg font-bold outline-none">Review payment</h2>
                {loading ? (
                    <p role="status" className="flex items-center gap-2 py-6 text-sm text-[var(--muted)]">
                        <Loader2 size={16} className="motion-safe:animate-spin" aria-hidden /> Checking the invoices…
                    </p>
                ) : (
                    <>
                        {items.length > 0 && <p className="mb-2 text-sm tabular-nums text-[var(--muted)]">{plural(items.length, "invoice")} · {totalsText(totals)}</p>}
                        {notice && (
                            <p role="alert" className="mb-2 flex gap-2 rounded-lg bg-[var(--warning-soft)] px-3 py-2 text-[13px] text-[var(--warning)]">
                                <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden /><span>{notice}</span>
                            </p>
                        )}
                        {sheet.error && <p role="alert" className="mb-2 rounded-lg bg-[var(--danger-soft)] px-3 py-2 text-[13px] text-[var(--danger)]">{sheet.error}</p>}
                        {items.length > 0 && (
                            <>
                                <ul className="mb-3 max-h-48 overflow-y-auto border-t border-[var(--border)]">
                                    {items.map(v => (
                                        <li key={v.invoiceId} className="flex justify-between gap-3 border-b border-[var(--border)] py-2 text-sm">
                                            <span className="min-w-0 [overflow-wrap:anywhere]">
                                                {label(v)}
                                                <span className="block text-[13px] text-[var(--muted)]">{[v.dueDate ? `Due ${v.dueDate}` : null, v.status].filter(Boolean).join(" · ")}</span>
                                            </span>
                                            <span className="whitespace-nowrap font-semibold tabular-nums">{money(v.amount ?? undefined, v.currency ?? undefined)}</span>
                                        </li>
                                    ))}
                                </ul>
                                <p className="mb-2 flex gap-1.5 text-[13px] text-[var(--success)]">
                                    <CheckCircle2 size={16} className="mt-0.5 shrink-0" aria-hidden />
                                    <span>No warning signs when each invoice was checked. We check each one again when you continue.</span>
                                </p>
                                {limited && (
                                    <p className="mb-2 text-[13px] text-[var(--muted)]">Some checks need earlier invoices from the same supplier and had none, so they were not run.</p>
                                )}
                                <p className="mb-1 text-[13px] text-[var(--muted)]">
                                    You pay on PayPal’s own page. Scam Copilot does not move money and cannot undo a payment. No warning signs is not a guarantee.
                                </p>
                            </>
                        )}
                        <div className="mt-3 grid grid-cols-[1fr_1.4fr] gap-2">
                            <button onClick={closeSheet} disabled={busy} className={`min-h-11 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3.5 font-semibold hover:bg-[var(--primary-soft)] disabled:opacity-60 ${FOCUS}`}>
                                {items.length > 0 ? "Cancel" : "Close"}
                            </button>
                            {items.length > 0 && (
                                <button
                                    onClick={() => { void confirm() }}
                                    disabled={busy}
                                    aria-busy={busy}
                                    className={`flex min-h-11 items-center justify-center gap-2 rounded-lg border border-[var(--primary)] bg-[var(--primary)] px-3.5 font-semibold text-white hover:brightness-110 disabled:cursor-progress disabled:opacity-75 ${FOCUS}`}
                                >
                                    {busy ? <><Loader2 size={16} className="motion-safe:animate-spin" aria-hidden /> Checking again…</> : "Continue to PayPal"}
                                </button>
                            )}
                        </div>
                    </>
                )}
            </section>
        </>
    )
}

import { useEffect, useRef, type KeyboardEvent } from "react"

export default function PayPalDemoModal({ onClose }: { onClose: () => void }) {
    const closeRef = useRef<HTMLButtonElement>(null)

    useEffect(() => {
        const previous = document.activeElement as HTMLElement | null
        closeRef.current?.focus()
        return () => previous?.focus()
    }, [])

    // Stops Escape here so it closes only the dialog, not the whole sidebar.
    const onKeyDown = (e: KeyboardEvent) => {
        if (e.key !== "Escape") return
        e.stopPropagation()
        onClose()
    }

    return (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
            <div
                role="dialog"
                aria-modal="true"
                aria-labelledby="paypal-demo-title"
                onClick={(e) => e.stopPropagation()}
                onKeyDown={onKeyDown}
                className="w-full max-w-sm rounded-2xl bg-[var(--card)] p-5 text-[var(--text)] shadow-xl"
            >
                <span className="mb-2 inline-block rounded bg-[var(--warning-soft)] px-2 py-0.5 text-[10px] font-bold uppercase text-[var(--warning)]">Demo</span>
                <h2 id="paypal-demo-title" className="mb-2 text-base font-semibold">PayPal integration is not connected</h2>
                <p className="mb-4 text-sm text-[var(--muted)]">
                    This is a demo. No request was sent to PayPal and nothing was verified. A real integration will be added later.
                </p>
                <button
                    ref={closeRef}
                    onClick={onClose}
                    className="w-full rounded-lg bg-[var(--primary)] px-3 py-2.5 text-sm font-semibold text-white hover:brightness-110 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"
                >
                    Got it
                </button>
            </div>
        </div>
    )
}

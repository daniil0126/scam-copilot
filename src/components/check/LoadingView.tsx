import { useEffect, useState } from "react"
import { Check, Loader2 } from "lucide-react"
import { ANALYSIS_STAGES } from "../../api/mock.js"

const STAGE_MS = 900

type Props = {
    onDone: () => void
    onCancel: () => void
}

export default function LoadingView({ onDone, onCancel }: Props) {
    const [active, setActive] = useState(0)

    useEffect(() => {
        const timer = setTimeout(
            () => (active >= ANALYSIS_STAGES.length - 1 ? onDone() : setActive(a => a + 1)),
            STAGE_MS,
        )
        return () => clearTimeout(timer)
    }, [active, onDone])

    return (
        <div className="flex flex-col items-center p-6 text-center" role="status" aria-live="polite">
            <Loader2 size={40} className="mb-4 text-[var(--primary)] motion-safe:animate-spin" aria-hidden />
            <h2 className="text-base font-semibold">Analysing the invoice...</h2>
            <p className="mb-5 mt-1 text-sm text-[var(--muted)]">Extracting data, checking payment details and comparing with history.</p>

            <ol className="mb-5 w-full space-y-2 text-left">
                {ANALYSIS_STAGES.map((label, i) => {
                    const done = i < active
                    const current = i === active
                    return (
                        <li key={label} className={`flex items-center gap-2.5 text-sm ${done || current ? "text-[var(--text)]" : "text-[var(--muted)]"} ${current ? "font-semibold" : ""}`}>
                            <span className={`flex h-5 w-5 items-center justify-center rounded-full border text-white ${done ? "border-[var(--success)] bg-[var(--success)]" : current ? "border-[var(--primary)]" : "border-[var(--border)]"}`}>
                                {done ? <Check size={12} aria-hidden /> : current ? <span className="h-2 w-2 rounded-full bg-[var(--primary)] motion-safe:animate-pulse" /> : null}
                            </span>
                            {label}
                            <span className="sr-only">{done ? "(done)" : current ? "(in progress)" : "(pending)"}</span>
                        </li>
                    )
                })}
            </ol>

            <button
                onClick={onCancel}
                className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-medium hover:bg-[var(--primary-soft)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"
            >
                Cancel
            </button>
        </div>
    )
}

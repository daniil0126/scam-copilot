import { Loader2 } from "lucide-react"
import type { TraceStep } from "../../api/types.js"
import TraceView from "./TraceView.js"

// What a screen reader hears: one short phrase for the step in progress, not the whole list again and again.
function announcement(steps: TraceStep[], canReadPayPal: boolean): string {
    const current = [...steps].reverse().find(s => s.state === "running") ?? steps[steps.length - 1]
    if (!current) return canReadPayPal ? "Thinking, PayPal may be checked" : "Thinking"
    return current.kind === "tool" ? `${current.label}${current.detail ? `, ${current.detail}` : ""}` : current.label
}

// Shown in the message list right after the question, where the answer will appear. When the answer arrives it takes
// this place and keeps the steps behind a "Show steps" button.
export default function LiveTrace({ steps, canReadPayPal }: { steps: TraceStep[]; canReadPayPal: boolean }) {
    return (
        <div className="mt-2 w-full max-w-[92%] shrink-0 self-start rounded-2xl border border-[var(--border)] bg-[var(--card)] px-3.5 py-3 text-[var(--text)]">
            <p role="status" aria-atomic="true" className="sr-only">{announcement(steps, canReadPayPal)}</p>
            {steps.length === 0 ? (
                <p className="flex items-center gap-2.5 text-sm">
                    <Loader2 size={16} className="motion-safe:animate-spin text-[var(--primary)]" aria-hidden />
                    {canReadPayPal ? "Thinking, PayPal may be checked…" : "Thinking…"}
                </p>
            ) : (
                <TraceView steps={steps} />
            )}
        </div>
    )
}

import { Check, Loader2, X } from "lucide-react"
import type { TraceStep } from "../../api/types.js"

// Colour is never the only signal: every state has its own icon, and a failure also says so in words.
const ICON = {
    running: <Loader2 size={16} className="motion-safe:animate-spin text-[var(--primary)]" aria-hidden />,
    done: <Check size={16} className="text-[var(--primary)]" aria-hidden />,
    failed: <X size={16} className="text-[var(--danger)]" aria-hidden />,
}

// The steps the assistant took, in order. Each is a real event from the server (a model turn or a PayPal read).
export default function TraceView({ steps }: { steps: TraceStep[] }) {
    return (
        <ol aria-label="Steps" className="space-y-2">
            {steps.map(step => (
                <li key={step.id} className="flex items-start gap-2.5">
                    <span className="mt-0.5 shrink-0">{ICON[step.state]}</span>
                    <span className="min-w-0 break-words [overflow-wrap:anywhere]">
                        <span className={`block text-sm leading-5 ${step.state === "running" ? "text-[var(--text)]" : "text-[var(--text)]"} ${step.kind === "tool" ? "font-medium" : ""}`}>
                            {step.label}
                            {step.state === "failed" && <span className="font-normal text-[var(--danger)]"> · failed</span>}
                        </span>
                        {step.detail && (
                            <span className="mt-0.5 block font-mono text-[13px] leading-5 text-[var(--muted)]">{step.detail}</span>
                        )}
                    </span>
                </li>
            ))}
        </ol>
    )
}

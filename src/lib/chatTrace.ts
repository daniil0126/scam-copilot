import type { ChatEvent, TraceStep } from "../api/types.js"

const argsText = (args: Record<string, string | number | boolean>) =>
    Object.entries(args).map(([k, v]) => `${k}=${String(v)}`).join(", ")

// Folds one event of the stream into the list of steps shown to the user.
export function applyEvent(steps: TraceStep[], event: ChatEvent): TraceStep[] {
    if (event.type === "model") {
        const label = event.first ? "Thinking" : "Reading the results"
        return upsert(steps, { id: event.id, kind: "model", label, state: event.state })
    }
    if (event.type === "tool") {
        return upsert(steps, {
            id: event.id, kind: "tool", label: event.local ? "Preparing the table" : `PayPal: ${event.name}`,
            detail: event.state === "running" ? argsText(event.args) : (event.summary ?? event.reason ?? "failed"),
            state: event.state,
        })
    }
    if (event.type === "fallback") {
        return upsert(steps, { id: "fallback", kind: "note", label: "Tools unavailable, answering without them", state: "done" })
    }
    return steps
}

function upsert(steps: TraceStep[], step: TraceStep): TraceStep[] {
    const at = steps.findIndex(s => s.id === step.id)
    if (at === -1) return [...steps, step]
    return steps.map((s, i) => (i === at ? { ...s, ...step, detail: step.detail ?? s.detail } : s))
}

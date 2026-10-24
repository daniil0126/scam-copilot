import { useCallback, useState } from "react"
import { HIGH_RISK_RESULT, LOW_RISK_RESULT } from "../../data/mock.js"
import type { VerificationResult } from "../../types.js"
import VerificationView from "./VerificationView.js"
import LoadingView from "./LoadingView.js"
import UploadCard from "./UploadCard.js"
import { validatePdf } from "../../lib/pdf.js"

type DemoState = "high" | "low"

const DEMO_RESULTS: Record<DemoState, VerificationResult> = { high: HIGH_RISK_RESULT, low: LOW_RISK_RESULT }

export default function CheckTab() {
    const [demo, setDemo] = useState<DemoState>("high")
    const [analysing, setAnalysing] = useState(false)

    const [file, setFile] = useState<File | null>(null)
    const [error, setError] = useState<string | null>(null)

    const finish = useCallback(() => setAnalysing(false), [])

    const selectFile = async (chosen: File) => {
        const problem = await validatePdf(chosen)
        setError(problem)
        setFile(problem ? null : chosen)
    }

    const clearFile = () => {
        setFile(null)
        setError(null)
        setAnalysing(false)
    }

    return (
        <div>
            {/* Demo-only controls: not part of the production design. */}
            <div role="group" aria-label="Demo state" className="flex items-center gap-1.5 border-b border-dashed border-[var(--border)] px-4 py-2 text-xs text-[var(--muted)]">
                <span className="mr-auto font-semibold uppercase tracking-wide">Demo</span>
                {(["high", "low"] as const).map(s => (
                    <button
                        key={s}
                        aria-pressed={demo === s}
                        onClick={() => { setDemo(s); setAnalysing(false) }}
                        className={`rounded px-2 py-1 font-medium focus-visible:outline-2 focus-visible:outline-[var(--primary)] ${demo === s ? "bg-[var(--primary-soft)] text-[var(--primary)]" : "hover:bg-[var(--primary-soft)]"}`}
                    >
                        {s === "high" ? "High risk" : "Low risk"}
                    </button>
                ))}
                <button
                    onClick={() => setAnalysing(true)}
                    className="rounded px-2 py-1 font-medium hover:bg-[var(--primary-soft)] focus-visible:outline-2 focus-visible:outline-[var(--primary)]"
                >
                    Run analysis
                </button>
            </div>

            <UploadCard file={file} error={error} onSelect={selectFile} onClear={clearFile} onAnalyse={() => setAnalysing(true)} />

            {analysing
                ? <LoadingView onDone={finish} onCancel={finish} />
                : <VerificationView key={demo} result={DEMO_RESULTS[demo]} />}
        </div>
    )
}

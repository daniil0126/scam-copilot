import { useCallback, useEffect, useRef, useState } from "react"
import { ScanSearch } from "lucide-react"
import { HIGH_RISK_RESULT } from "../../api/mock.js"
import type { CheckSource, VerificationResult } from "../../api/types.js"
import VerificationView from "./VerificationView.js"
import LoadingView from "./LoadingView.js"
import UploadCard from "./UploadCard.js"
import PageCheckCard from "./PageCheckCard.js"
import SourceBar from "./SourceBar.js"
import { validatePdf } from "../../lib/pdf.js"

type Shown = { result: VerificationResult; sample: boolean; source?: CheckSource }

type Props = {
    onOpenHistory: () => void
    // Id of the stored check on screen (null for none or for sample data), used as chat context.
    onShownChange: (id: string | null) => void
}

export default function CheckTab({ onOpenHistory, onShownChange }: Props) {
    const [analysing, setAnalysing] = useState(false)
    const [shown, setShown] = useState<Shown | null>(null)

    useEffect(() => {
        onShownChange(shown && !shown.sample ? shown.result.id : null)
    }, [shown, onShownChange])

    // The result is drawn below the check and upload cards, usually under the fold: bring it into view and move focus to it,
    // so that a keyboard or screen reader user lands on it too.
    const resultRef = useRef<HTMLDivElement>(null)
    useEffect(() => {
        const el = resultRef.current
        if (!shown || !el) return
        const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
        el.scrollIntoView({ block: "start", behavior: reduceMotion ? "auto" : "smooth" })
        el.focus({ preventScroll: true })
    }, [shown])

    const [file, setFile] = useState<File | null>(null)
    const [error, setError] = useState<string | null>(null)

    // PDF analysis is not connected yet: after the animation it shows sample data, clearly labelled.
    const finishPdfDemo = useCallback(() => {
        setAnalysing(false)
        setShown({ result: HIGH_RISK_RESULT, sample: true })
    }, [])
    const cancelAnalysis = useCallback(() => setAnalysing(false), [])

    const selectFile = async (chosen: File) => {
        const problem = await validatePdf(chosen)
        setError(problem)
        setFile(problem ? null : chosen)
    }

    const clearFile = () => {
        setFile(null)
        setError(null)
        setAnalysing(false)
        setShown(s => (s?.sample ? null : s))
    }

    return (
        <div>
            <PageCheckCard onOpenHistory={onOpenHistory} onResult={(result, source) => { setAnalysing(false); setShown({ result, sample: false, source }) }} />

            <UploadCard file={file} error={error} onSelect={selectFile} onClear={clearFile} onAnalyse={() => { setShown(null); setAnalysing(true) }} />

            {analysing ? (
                <LoadingView onDone={finishPdfDemo} onCancel={cancelAnalysis} />
            ) : shown ? (
                <div ref={resultRef} tabIndex={-1} role="region" aria-label="Check result" className="outline-none">
                    {shown.sample && (
                        <p role="note" className="mx-4 mt-4 rounded-lg bg-[var(--warning-soft)] px-3 py-2 text-xs font-medium text-[var(--warning)]">
                            Sample data: PDF analysis is not connected yet.
                        </p>
                    )}
                    {shown.source && <SourceBar source={shown.source} result={shown.result} />}
                    <VerificationView key={shown.result.id} result={shown.result} sample={shown.sample} />
                </div>
            ) : (
                <div className="flex flex-col items-center gap-2 p-10 text-center text-[var(--muted)]">
                    <ScanSearch size={32} aria-hidden />
                    <p className="text-sm">Open a PayPal invoice and press the button above to check it.</p>
                </div>
            )}
        </div>
    )
}

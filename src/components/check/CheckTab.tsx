import { useCallback, useEffect, useState } from "react"
import { ScanSearch } from "lucide-react"
import { HIGH_RISK_RESULT } from "../../api/mock.js"
import type { VerificationResult } from "../../api/types.js"
import VerificationView from "./VerificationView.js"
import LoadingView from "./LoadingView.js"
import UploadCard from "./UploadCard.js"
import PageCheckCard from "./PageCheckCard.js"
import { validatePdf } from "../../lib/pdf.js"

type Shown = { result: VerificationResult; sample: boolean }

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
            <PageCheckCard onOpenHistory={onOpenHistory} onResult={(result) => { setAnalysing(false); setShown({ result, sample: false }) }} />

            <UploadCard file={file} error={error} onSelect={selectFile} onClear={clearFile} onAnalyse={() => { setShown(null); setAnalysing(true) }} />

            {analysing ? (
                <LoadingView onDone={finishPdfDemo} onCancel={cancelAnalysis} />
            ) : shown ? (
                <>
                    {shown.sample && (
                        <p role="note" className="mx-4 mt-4 rounded-lg bg-[var(--warning-soft)] px-3 py-2 text-xs font-medium text-[var(--warning)]">
                            Sample data: PDF analysis is not connected yet.
                        </p>
                    )}
                    <VerificationView key={shown.result.id} result={shown.result} />
                </>
            ) : (
                <div className="flex flex-col items-center gap-2 p-10 text-center text-[var(--muted)]">
                    <ScanSearch size={32} aria-hidden />
                    <p className="text-sm">Open a PayPal invoice and press the button above to check it.</p>
                </div>
            )}
        </div>
    )
}

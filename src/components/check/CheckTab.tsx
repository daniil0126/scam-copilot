import { useEffect, useRef, useState } from "react"
import { ScanSearch } from "lucide-react"
import type { CheckSource, VerificationResult } from "../../api/types.js"
import { explainCheck } from "../../api/client.js"
import VerificationView from "./VerificationView.js"
import PageCheckCard from "./PageCheckCard.js"
import SourceBar from "./SourceBar.js"

type Shown = { result: VerificationResult; source?: CheckSource }

type Props = {
    onOpenHistory: () => void
    // Id of the stored check on screen (null for none), used as chat context.
    onShownChange: (id: string | null) => void
}

export default function CheckTab({ onOpenHistory, onShownChange }: Props) {
    const [shown, setShown] = useState<Shown | null>(null)
    // The rules answer at once; the AI explanation follows when the model is done and is added to what is on screen.
    const [explaining, setExplaining] = useState(false)
    const latest = useRef<string | null>(null)

    const show = (result: VerificationResult, source: CheckSource) => {
        setShown({ result, source })
        latest.current = result.id
        if (result.ai || result.level === "low") { setExplaining(false); return }
        setExplaining(true)
        explainCheck(result.id)
            .then(full => { if (latest.current === result.id) setShown(prev => prev && prev.result.id === full.id ? { ...prev, result: full } : prev) })
            .catch(() => {})  // the rule-based result stands on its own
            .finally(() => { if (latest.current === result.id) setExplaining(false) })
    }

    useEffect(() => {
        onShownChange(shown ? shown.result.id : null)
    }, [shown, onShownChange])

    // The result is drawn below the check card, usually under the fold: bring it into view and move focus to it,
    // so that a keyboard or screen reader user lands on it too.
    const resultRef = useRef<HTMLDivElement>(null)
    useEffect(() => {
        const el = resultRef.current
        if (!shown || !el) return
        const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
        el.scrollIntoView({ block: "start", behavior: reduceMotion ? "auto" : "smooth" })
        el.focus({ preventScroll: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps, react-x/exhaustive-deps -- only a different check scrolls; its explanation arriving must not
    }, [shown?.result.id])

    return (
        <div>
            <PageCheckCard onOpenHistory={onOpenHistory} onResult={show} />

            {shown ? (
                <div ref={resultRef} tabIndex={-1} role="region" aria-label="Check result" className="outline-none">
                    {shown.source && <SourceBar source={shown.source} result={shown.result} />}
                    <VerificationView key={shown.result.id} result={shown.result} explaining={explaining} />
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

import { useState } from "react"
import { ChevronDown, Sparkles } from "lucide-react"
import type { VerificationResult } from "../../api/types.js"
import { LEVEL_META, alertTitle } from "../../lib/risk.js"
import RiskSummary from "./RiskSummary.js"
import ComparisonTable from "./ComparisonTable.js"
import RecommendationCard from "./RecommendationCard.js"
import VerificationActions from "./VerificationActions.js"
import PayPalDemoModal from "./PayPalDemoModal.js"
import { groupFindings } from "../../lib/groupResult.js"

export default function VerificationView({ result, sample = false }: { result: VerificationResult, sample?: boolean }) {
    const [alertOpen, setAlertOpen] = useState(true)
    const [diffOpen, setDiffOpen] = useState(true)
    const [detailsOpen, setDetailsOpen] = useState(false)
    const [paypalOpen, setPaypalOpen] = useState(false)

    const meta = LEVEL_META[result.level]
    const { title, subtitle } = alertTitle(result.level, groupFindings(result.findings).flagged.length)
    const Icon = meta.icon

    return (
        <div className="flex flex-col gap-3 p-4">
            <section className={`rounded-xl border ${meta.border} ${meta.soft}`}>
                <button
                    onClick={() => setAlertOpen(o => !o)}
                    aria-expanded={alertOpen}
                    className="flex w-full items-center gap-3 p-3 text-left focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--primary)]"
                >
                    <Icon size={24} className={meta.text} aria-hidden />
                    <span className="flex-1">
                        <span className={`block text-sm font-semibold ${meta.text}`}>{title}</span>
                        <span className="block text-xs text-[var(--muted)]">{subtitle}</span>
                    </span>
                    <ChevronDown size={18} className={`text-[var(--muted)] transition-transform ${alertOpen ? "rotate-180" : ""}`} aria-hidden />
                </button>
            </section>

            {alertOpen && <RiskSummary result={result} />}

            {result.comparison.length > 0 && (
                <section>
                    <button
                        onClick={() => setDiffOpen(o => !o)}
                        aria-expanded={diffOpen}
                        className="mb-2 flex w-full items-center justify-between text-sm font-semibold focus-visible:outline-2 focus-visible:outline-[var(--primary)]"
                    >
                        Comparison
                        <ChevronDown size={16} className={`text-[var(--muted)] transition-transform ${diffOpen ? "rotate-180" : ""}`} aria-hidden />
                    </button>
                    {diffOpen && <ComparisonTable rows={result.comparison} />}
                </section>
            )}

            {result.ai && (
                <section aria-label="AI review" className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
                    <h3 className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                        <Sparkles size={14} aria-hidden /> AI review
                    </h3>
                    <p className="text-sm">{result.ai.summary}</p>
                </section>
            )}

            <RecommendationCard text={result.recommendation} />

            {detailsOpen && (
                <section aria-label="Details" className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
                    <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Evidence</h3>
                    <ul className="list-disc space-y-1 pl-4 text-sm">
                        {result.evidence.map(line => <li key={line}>{line}</li>)}
                    </ul>
                </section>
            )}

            <VerificationActions
                detailsOpen={detailsOpen}
                onToggleDetails={() => setDetailsOpen(o => !o)}
                onCheckPayPal={() => setPaypalOpen(true)}
            />

            <p className="text-[11px] leading-snug text-[var(--muted)]">
                {sample && "Sample analysis data for demonstration. "}The score is not a calibrated probability of fraud, and differences do not prove fraud.
                {result.level === "low" && " Only the available signals were checked, so a low score does not guarantee the invoice is safe."}
            </p>

            {paypalOpen && <PayPalDemoModal onClose={() => setPaypalOpen(false)} />}
        </div>
    )
}

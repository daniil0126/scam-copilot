import type { VerificationResult } from "../../types.js"
import RiskIndicator from "./RiskIndicator.js"
import FindingsList from "./FindingsList.js"

export default function RiskSummary({ result }: { result: VerificationResult }) {
    return (
        <div className="flex items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <RiskIndicator score={result.score} level={result.level} />
            <FindingsList findings={result.findings} />
        </div>
    )
}

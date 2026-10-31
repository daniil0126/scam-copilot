import type { VerificationResult } from "../../api/types.js"
import RiskIndicator from "./RiskIndicator.js"
import FindingsList from "./FindingsList.js"
import { groupFindings } from "../../lib/groupResult.js"

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

export default function RiskSummary({ result }: { result: VerificationResult }) {
    const { flagged, passed, notChecked } = groupFindings(result.findings)
    const counts = [
        flagged.length > 0 && plural(flagged.length, "sign to look at", "signs to look at"),
        passed.length > 0 && `${passed.length} passed`,
        notChecked.length > 0 && `${notChecked.length} not checked`,
    ].filter(Boolean).join(" · ")
    return (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <div className="mb-4 flex items-center gap-4 border-b border-[var(--border)] pb-4">
                <RiskIndicator score={result.score} level={result.level} />
                <p className="text-sm text-[var(--muted)]">{counts || "No findings"}</p>
            </div>
            <FindingsList findings={result.findings} />
        </div>
    )
}

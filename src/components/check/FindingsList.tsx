import { AlertCircle, AlertTriangle, CheckCircle2 } from "lucide-react"
import type { Finding, FindingSeverity } from "../../types.js"
import { SEVERITY_TEXT } from "../../lib/risk.js"

const ICONS: Record<FindingSeverity, typeof AlertCircle> = {
    high: AlertCircle,
    medium: AlertTriangle,
    low: CheckCircle2,
    ok: CheckCircle2,
}

export default function FindingsList({ findings }: { findings: Finding[] }) {
    return (
        <ul className="flex flex-1 flex-col gap-2">
            {findings.map(({ id, label, severity }) => {
                const Icon = ICONS[severity]
                return (
                    <li key={id} className="flex items-center gap-2 text-sm font-medium text-[var(--text)]">
                        <Icon size={16} className={`shrink-0 ${SEVERITY_TEXT[severity]}`} aria-hidden />
                        {label}
                    </li>
                )
            })}
        </ul>
    )
}

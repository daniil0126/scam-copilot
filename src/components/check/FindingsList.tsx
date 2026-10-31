import { AlertCircle, AlertTriangle, CheckCircle2, ChevronDown, CircleHelp } from "lucide-react"
import type { Finding } from "../../api/types.js"
import { groupFindings } from "../../lib/groupResult.js"

function GroupTitle({ children }: { children: string }) {
    return <h4 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]">{children}</h4>
}

function FlaggedItem({ finding }: { finding: Finding }) {
    const high = finding.severity === "high"
    const Icon = high ? AlertCircle : AlertTriangle
    const tone = high ? "text-[var(--danger)]" : "text-[var(--warning)]"
    const pill = high ? "bg-[var(--danger-soft)] text-[var(--danger)]" : "bg-[var(--warning-soft)] text-[var(--warning)]"
    const head = (
        <span className="flex items-start gap-2">
            <Icon size={16} className={`mt-0.5 shrink-0 ${tone}`} aria-hidden />
            <span className="flex-1 text-sm font-medium text-[var(--text)]">{finding.label}</span>
            <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold ${pill}`}>{high ? "High" : "Medium"}</span>
        </span>
    )
    if (!finding.detail) return <li>{head}</li>
    return (
        <li>
            <details open={high} className="group">
                <summary className="flex cursor-pointer list-none items-start gap-1 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)] [&::-webkit-details-marker]:hidden">
                    <span className="flex-1">{head}</span>
                    <ChevronDown size={14} className="mt-1 shrink-0 text-[var(--muted)] transition-transform group-open:rotate-180" aria-label="Show why" />
                </summary>
                <p className="mt-1 pl-6 text-xs leading-snug text-[var(--muted)]">{finding.detail}</p>
            </details>
        </li>
    )
}

export default function FindingsList({ findings }: { findings: Finding[] }) {
    const { flagged, passed, notChecked } = groupFindings(findings)
    return (
        <div className="flex flex-col gap-4">
            {flagged.length > 0 && (
                <section aria-label="Signs to look at">
                    <GroupTitle>Needs attention</GroupTitle>
                    <ul className="flex flex-col gap-2.5">{flagged.map(f => <FlaggedItem key={f.id} finding={f} />)}</ul>
                </section>
            )}
            {notChecked.length > 0 && (
                <section aria-label="Checks that could not be done">
                    <GroupTitle>Not checked</GroupTitle>
                    <ul className="flex flex-col gap-1.5">
                        {notChecked.map(f => (
                            <li key={f.id} className="flex items-start gap-2 text-sm text-[var(--muted)]">
                                <CircleHelp size={16} className="mt-0.5 shrink-0" aria-hidden />
                                <span>{f.label}{f.detail && <span className="block text-xs leading-snug">{f.detail}</span>}</span>
                            </li>
                        ))}
                    </ul>
                </section>
            )}
            {passed.length > 0 && (
                <section aria-label="Checks that passed">
                    <GroupTitle>Passed</GroupTitle>
                    <ul className="flex flex-col gap-1.5">
                        {passed.map(f => (
                            <li key={f.id} className="flex items-center gap-2 text-sm text-[var(--text)]">
                                <CheckCircle2 size={16} className="shrink-0 text-[var(--success)]" aria-hidden />
                                {f.label}
                            </li>
                        ))}
                    </ul>
                </section>
            )}
        </div>
    )
}

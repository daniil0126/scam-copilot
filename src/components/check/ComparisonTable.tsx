import type { ComparisonRow } from "../../api/types.js"
import { groupRows } from "../../lib/groupResult.js"

function Value({ text, differs }: { text: string; differs: boolean }) {
    if (!text) return <span className="text-xs italic text-[var(--muted)]">Not shown</span>
    return <span className={`break-all text-sm ${differs ? "font-semibold text-[var(--danger)]" : "text-[var(--text)]"}`}>{text}</span>
}

export default function ComparisonTable({ rows }: { rows: ComparisonRow[] }) {
    return (
        <div className="flex flex-col gap-3">
            {groupRows(rows).map(group => (
                <section key={group.title} aria-label={group.title} className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
                    <h4 className="border-b border-[var(--border)] px-3 py-2 text-xs font-semibold text-[var(--muted)]">{group.title}</h4>
                    <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-x-3 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--muted)]">
                        <span>{group.now}</span>
                        <span>{group.before}</span>
                    </div>
                    {group.rows.map(({ field, current, previous, differs }) => (
                        <div key={field} className="border-t border-[var(--border)] px-3 py-2">
                            <div className="mb-1 flex items-center justify-between text-xs font-medium text-[var(--muted)]">
                                {field}
                                {differs && <span className="rounded bg-[var(--danger-soft)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--danger)]">Differs</span>}
                            </div>
                            <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-x-3">
                                <Value text={current} differs={differs} />
                                <Value text={previous} differs={false} />
                            </div>
                        </div>
                    ))}
                </section>
            ))}
        </div>
    )
}

import type { TabId } from "../../api/types.js"

export const TABS: { id: TabId, label: string }[] = [
    { id: "check", label: "Check" },
    { id: "monitor", label: "Monitor" },
    { id: "history", label: "History" },
    { id: "chat", label: "Chat" },
]  // Settings is opened from the gear in the header

export type TabBadge = { count: number; urgent: boolean }

type Props = {
    tab: TabId
    onChange: (tab: TabId) => void
    badges?: Partial<Record<TabId, TabBadge>>
}

export default function SidebarTabs({ tab, onChange, badges }: Props) {
    return (
        <nav role="tablist" aria-label="Scam Copilot sections" className="flex border-b border-[var(--border)] bg-[var(--card)]">
            {TABS.map(({ id, label }) => {
                const active = tab === id
                const badge = badges?.[id]
                return (
                    <button
                        key={id}
                        role="tab"
                        aria-selected={active}
                        onClick={() => onChange(id)}
                        className={`flex-1 border-b-2 px-2 py-3 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--primary)] ${active
                            ? "border-[var(--primary)] font-semibold text-[var(--primary)]"
                            : "border-transparent text-[var(--muted)] hover:text-[var(--text)]"}`}
                    >
                        {label}
                        {badge && badge.count > 0 && (
                            <span
                                aria-label={`${badge.count} new${badge.urgent ? ", some high risk" : ""}`}
                                className={`ml-1.5 inline-flex min-w-5 items-center justify-center rounded-full px-1.5 text-xs font-bold tabular-nums text-white ${badge.urgent ? "bg-[var(--danger)]" : "bg-[var(--primary)]"}`}
                            >
                                {badge.count > 9 ? "9+" : badge.count}
                            </span>
                        )}
                    </button>
                )
            })}
        </nav>
    )
}

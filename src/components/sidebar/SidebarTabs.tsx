import type { TabId } from "../../api/types.js"

export const TABS: { id: TabId, label: string }[] = [
    { id: "check", label: "Check" },
    { id: "history", label: "History" },
    { id: "chat", label: "Chat" },
    { id: "settings", label: "Settings" },
]

type Props = {
    tab: TabId
    onChange: (tab: TabId) => void
}

export default function SidebarTabs({ tab, onChange }: Props) {
    return (
        <nav role="tablist" aria-label="Scam Copilot sections" className="flex border-b border-[var(--border)] bg-[var(--card)]">
            {TABS.map(({ id, label }) => {
                const active = tab === id
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
                    </button>
                )
            })}
        </nav>
    )
}

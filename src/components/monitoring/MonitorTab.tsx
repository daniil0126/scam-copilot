import { useState } from "react"
import type { MonitorSection } from "../../api/types.js"
import AlertsView from "../alerts/AlertsView.js"
import type { UnreadCount } from "../alerts/useUnreadCount.js"
import MonthlyReportView from "../reports/MonthlyReportView.js"
import MonitoringCard from "./MonitoringCard.js"
import type { Monitoring } from "./useMonitoring.js"

const SECTIONS: { id: MonitorSection; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "alerts", label: "Alerts" },
    { id: "report", label: "Report" },
]

type Props = {
    monitoring: Monitoring
    alerts: UnreadCount
    highlightSince: string
    onOpenCheck: (checkId: string) => void
}

// The Monitor tab: live state, the alerts the backend raised, and the monthly report.
export default function MonitorTab({ monitoring, alerts, highlightSince, onOpenCheck }: Props) {
    const [section, setSection] = useState<MonitorSection>("overview")

    return (
        <div>
            <div role="tablist" aria-label="Monitor sections" className="mx-3 mt-3 flex rounded-lg border border-[var(--border)] bg-[var(--card)] p-0.5">
                {SECTIONS.map(({ id, label }) => {
                    const active = section === id
                    return (
                        <button
                            key={id}
                            role="tab"
                            aria-selected={active}
                            onClick={() => setSection(id)}
                            className={`flex-1 cursor-pointer rounded-md px-2 py-1.5 text-xs font-semibold transition-colors focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--primary)] ${active
                                ? "bg-[var(--primary-soft)] text-[var(--primary)]"
                                : "text-[var(--muted)] hover:text-[var(--text)]"}`}
                        >
                            {label}
                            {id === "alerts" && alerts.unread > 0 && (
                                <span aria-label={`${alerts.unread} unread`} className="ml-1.5 inline-flex min-w-4 items-center justify-center rounded-full bg-[var(--primary)] px-1 text-[11px] font-bold tabular-nums text-white">
                                    {alerts.unread > 99 ? "99+" : alerts.unread}
                                </span>
                            )}
                        </button>
                    )
                })}
            </div>
            {section === "overview" && <MonitoringCard {...monitoring} highlightSince={highlightSince} />}
            {section === "alerts" && <AlertsView reloadKey={alerts.unread} onRead={() => void alerts.refresh()} onOpenCheck={onOpenCheck} />}
            {section === "report" && <MonthlyReportView onOpenCheck={onOpenCheck} />}
        </div>
    )
}

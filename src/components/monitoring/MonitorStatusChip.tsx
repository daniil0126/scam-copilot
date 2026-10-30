import type { MonitoringStatus } from "../../api/types.js"
import { STATE_META } from "./monitoringMeta.js"

type Props = {
    status: MonitoringStatus | null
    onClick: () => void
}

// Always visible in the header so a paused or failing monitor is noticed on every tab.
export default function MonitorStatusChip({ status, onClick }: Props) {
    if (!status) return null
    const meta = STATE_META[status.state]
    return (
        <button
            onClick={onClick}
            aria-label={`Monitoring ${meta.label.toLowerCase()}. Open the monitor`}
            className="flex cursor-pointer items-center gap-1.5 rounded-full bg-white/10 px-2.5 py-1 text-xs font-semibold text-white transition-colors hover:bg-white/20 focus-visible:outline-2 focus-visible:outline-white"
        >
            <span aria-hidden className="relative flex h-2 w-2">
                {status.state === "ACTIVE" && <span className={`absolute inline-flex h-full w-full rounded-full opacity-60 motion-safe:animate-ping ${meta.dot}`} />}
                <span className={`relative inline-flex h-2 w-2 rounded-full ${meta.dot}`} />
            </span>
            {meta.label}
        </button>
    )
}

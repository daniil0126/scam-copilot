import { X } from "lucide-react"
import type { AppNotification } from "../../api/types.js"
import { ALERT_LEVEL_META, formatMoney } from "../../lib/risk.js"

type Props = { alert: AppNotification; onOpen: () => void; onDismiss: () => void }

// A new alert, over the panel whatever tab is open. It stays until it is opened or dismissed: an alert about a possible
// scam must not vanish on a timer while the person is looking at something else.
export default function AlertToast({ alert, onOpen, onDismiss }: Props) {
    const risk = ALERT_LEVEL_META[alert.riskLevel]
    const inv = alert.invoice
    const detail = [inv?.supplierName, inv?.amount != null && inv.currency ? formatMoney(inv.amount, inv.currency) : null].filter(Boolean).join(" · ")
    return (
        <div
            role="alert"
            className={`sc-toast-in absolute inset-x-3 top-[3.25rem] z-10 flex items-start gap-3 rounded-xl border ${risk.border} bg-[var(--card)] p-3 shadow-2xl`}
            style={{ borderLeftWidth: 4, borderLeftColor: risk.stroke }}
        >
            <span aria-hidden className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md ${risk.soft} ${risk.text}`}>
                <risk.icon size={18} />
            </span>
            <div className="min-w-0 flex-1">
                <p className={`text-sm font-bold ${risk.text}`}>New alert · {risk.label}</p>
                {detail && <p className="break-words text-sm text-[var(--text)]">{detail}</p>}
                <button
                    onClick={onOpen}
                    className="mt-1.5 rounded-md bg-[var(--primary)] px-2.5 py-1 text-xs font-semibold text-white hover:brightness-110 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"
                >
                    View alert
                </button>
            </div>
            <button aria-label="Dismiss alert" onClick={onDismiss} className="-m-1 rounded-md p-2 text-[var(--muted)] hover:text-[var(--text)] focus-visible:outline-2 focus-visible:outline-[var(--primary)]">
                <X size={16} aria-hidden />
            </button>
        </div>
    )
}

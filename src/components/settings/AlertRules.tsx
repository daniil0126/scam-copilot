import { useEffect, useState } from "react"
import { AlertOctagon, ShieldAlert } from "lucide-react"
import { fetchAlertSettings, saveAlertSettings } from "../../api/client.js"
import type { AlertEventType, AlertSettings } from "../../api/types.js"

const CATEGORIES: { id: AlertEventType; label: string }[] = [
    { id: "CRITICAL_RISK", label: "Critical risk" },
    { id: "HIGH_RISK", label: "High risk" },
    { id: "VENDOR_IMPERSONATION", label: "Vendor impersonation" },
    { id: "POTENTIAL_DUPLICATE", label: "Possible duplicate" },
    { id: "SUSPICIOUS_PAYMENT_LINK", label: "Suspicious payment link" },
]

const THRESHOLDS: { id: AlertSettings["alertThreshold"]; label: string; icon: typeof ShieldAlert }[] = [
    { id: "HIGH", label: "High and above", icon: ShieldAlert },
    { id: "CRITICAL", label: "Critical only", icon: AlertOctagon },
]

// Alert rules live on the server (they decide which stored checks raise an alert), not in this browser's settings.
export default function AlertRules() {
    const [rules, setRules] = useState<AlertSettings | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [saving, setSaving] = useState(false)

    useEffect(() => {
        let cancelled = false
        fetchAlertSettings()
            .then(next => { if (!cancelled) setRules(next) })
            .catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : "Could not load the alert rules.") })
        return () => { cancelled = true }
    }, [])

    // The change shows at once and goes back if the server refuses it.
    const change = async (patch: { alertThreshold?: AlertSettings["alertThreshold"]; categories?: Partial<AlertSettings["categories"]> }) => {
        if (!rules) return
        const previous = rules
        const next: AlertSettings = {
            alertThreshold: patch.alertThreshold ?? rules.alertThreshold,
            categories: { ...rules.categories, ...patch.categories },
        }
        setRules(next)
        setSaving(true)
        try {
            setRules(await saveAlertSettings({ alertThreshold: next.alertThreshold, categories: patch.categories ?? {} }))
            setError(null)
        } catch (e) {
            setRules(previous)
            setError(e instanceof Error ? e.message : "Could not save the alert rules.")
        } finally {
            setSaving(false)
        }
    }

    return (
        <div aria-busy={saving}>
            {error && <p role="alert" className="mb-2 rounded-lg bg-[var(--danger-soft)] px-3 py-2 text-xs font-medium text-[var(--danger)]">{error}</p>}
            {!rules && !error && <p role="status" className="text-sm text-[var(--muted)]">Loading…</p>}
            {rules && (
                <>
                    <div role="radiogroup" aria-label="Risk alert threshold" className="grid grid-cols-2 gap-2">
                        {THRESHOLDS.map(({ id, label, icon: Icon }) => {
                            const active = rules.alertThreshold === id
                            return (
                                <button
                                    key={id}
                                    role="radio"
                                    aria-checked={active}
                                    disabled={saving}
                                    onClick={() => void change({ alertThreshold: id })}
                                    className={`flex items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-[var(--primary)] disabled:opacity-60 ${active
                                        ? "border-[var(--primary)] bg-[var(--primary-soft)] text-[var(--primary)]"
                                        : "border-[var(--border)] bg-[var(--card)] text-[var(--text)] hover:bg-[var(--primary-soft)]"}`}
                                >
                                    <Icon size={16} aria-hidden /> {label}
                                </button>
                            )
                        })}
                    </div>
                    <ul className="mt-2 flex flex-col gap-2">
                        {CATEGORIES.map(({ id, label }) => (
                            <li key={id}>
                                <label className="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-3">
                                    <span className="text-sm text-[var(--text)]">{label}</span>
                                    <input
                                        type="checkbox"
                                        role="switch"
                                        checked={rules.categories[id] ?? true}
                                        disabled={saving}
                                        onChange={e => void change({ categories: { [id]: e.target.checked } })}
                                        className="peer sr-only"
                                    />
                                    <span className="relative h-6 w-10 shrink-0 rounded-full bg-[var(--border)] transition-colors after:absolute after:left-0.5 after:top-0.5 after:h-5 after:w-5 after:rounded-full after:bg-white after:shadow after:transition-transform peer-checked:bg-[var(--primary)] peer-checked:after:translate-x-4 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-[var(--primary)] peer-disabled:opacity-60" />
                                </label>
                            </li>
                        ))}
                    </ul>
                    <p className="mt-1 text-[11px] leading-snug text-[var(--muted)]">
                        Applies to invoices checked from now on. Alerts already raised stay.
                    </p>
                </>
            )}
        </div>
    )
}

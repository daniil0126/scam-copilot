import { Activity, AlertTriangle, Loader2, Pause, Play, RefreshCw } from "lucide-react"
import type { Monitoring } from "./useMonitoring.js"
import MonitorEventsGrid from "./MonitorEventsGrid.js"
import { STATE_META } from "./monitoringMeta.js"

const clock = (iso: string | null, seconds = false) =>
    iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", ...(seconds && { second: "2-digit" }) }) : "never"

// `highlightSince`: events detected after this moment are marked as new.
export default function MonitoringCard({ status, summary, error, busy, sync, toggle, highlightSince }: Monitoring & { highlightSince: string }) {
    if (!status) {
        return error
            ? <p role="alert" className="m-3 rounded-lg bg-[var(--danger-soft)] px-3 py-2 text-sm font-medium text-[var(--danger)]">{error}</p>
            : <p role="status" className="p-10 text-center text-sm text-[var(--muted)]">Loading monitoring…</p>
    }

    const meta = STATE_META[status.state]
    const paused = status.state === "PAUSED"
    const live = status.state === "ACTIVE"
    const highRisk = status.highRisk + status.criticalRisk
    const spoken = `Monitoring ${paused ? "paused" : live ? "live" : "has a problem"}. ${status.totalInvoices} invoices, ${highRisk} high risk.`

    const button = "inline-flex min-h-8 flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)] cursor-pointer"

    return (
        <section aria-label="Background monitoring" className="m-3 overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-sm">
            {/* One status region, announced as a whole phrase only when the state or the counts change. */}
            <p role="status" aria-atomic="true" className="sr-only">{spoken}</p>

            <header className="flex items-center justify-between gap-3 px-4 pt-4">
                <div className="flex min-w-0 items-center gap-3">
                    <span className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--primary-soft)] text-[var(--primary)]">
                        <Activity size={18} aria-hidden />
                        <span className="absolute -right-0.5 -top-0.5 flex h-3 w-3">
                            {live && <span aria-hidden className={`absolute inline-flex h-full w-full rounded-full opacity-60 motion-safe:animate-ping ${meta.dot}`} />}
                            <span aria-hidden className={`relative inline-flex h-3 w-3 rounded-full border-2 border-[var(--card)] ${meta.dot}`} />
                        </span>
                    </span>
                    <div className="min-w-0">
                        <h2 className="text-sm font-bold leading-tight">Invoice monitoring</h2>
                        <p className="truncate text-xs text-[var(--muted)]">Updated {clock(status.lastSuccessfulSyncAt, true)}</p>
                    </div>
                </div>
                <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ${meta.pill}`}>{meta.label}</span>
            </header>

            <dl className="mt-4 grid grid-cols-2 gap-2 px-4">
                <div className="rounded-lg bg-[var(--bg)] px-3 py-2">
                    <dt className="text-xs text-[var(--muted)]">Invoices watched</dt>
                    <dd className="text-xl font-bold tabular-nums">{status.totalInvoices}</dd>
                </div>
                <div className={`rounded-lg px-3 py-2 ${highRisk > 0 ? "bg-[var(--danger-soft)]" : "bg-[var(--bg)]"}`}>
                    <dt className="text-xs text-[var(--muted)]">High risk</dt>
                    <dd className={`text-xl font-bold tabular-nums ${highRisk > 0 ? "text-[var(--danger)]" : ""}`}>{highRisk}</dd>
                </div>
                {/* Counted from the stored analyses; the monitor's own counters do not know these two yet. */}
                {summary && (
                    <>
                        <div className={`rounded-lg px-3 py-2 ${summary.potentialDuplicates > 0 ? "bg-[var(--warning-soft)]" : "bg-[var(--bg)]"}`}>
                            <dt className="text-xs text-[var(--muted)]">Possible duplicates</dt>
                            <dd className="text-xl font-bold tabular-nums">{summary.potentialDuplicates}</dd>
                        </div>
                        <div className={`rounded-lg px-3 py-2 ${summary.vendorAnomalies > 0 ? "bg-[var(--warning-soft)]" : "bg-[var(--bg)]"}`}>
                            <dt className="text-xs text-[var(--muted)]">Vendor anomalies</dt>
                            <dd className="text-xl font-bold tabular-nums">{summary.vendorAnomalies}</dd>
                        </div>
                    </>
                )}
            </dl>

            <div className="mt-3 flex gap-2 px-4">
                <button
                    className={`${button} bg-[var(--primary)] text-white hover:opacity-90`}
                    disabled={busy !== null || paused}
                    onClick={() => void sync()}
                >
                    {busy === "sync" ? <Loader2 size={14} aria-hidden className="motion-safe:animate-spin" /> : <RefreshCw size={14} aria-hidden />}
                    Check now
                </button>
                <button
                    className={`${button} border border-[var(--border)] text-[var(--text)] hover:bg-[var(--primary-soft)]`}
                    disabled={busy !== null}
                    aria-pressed={paused}
                    onClick={() => void toggle()}
                >
                    {busy === "toggle" ? <Loader2 size={14} aria-hidden className="motion-safe:animate-spin" /> : paused ? <Play size={14} aria-hidden /> : <Pause size={14} aria-hidden />}
                    {paused ? "Resume" : "Pause"}
                </button>
            </div>

            {(error || status.errors.length > 0) && (
                <div role="alert" className="mx-4 mt-3 flex gap-2 rounded-lg bg-[var(--danger-soft)] px-3 py-2 text-xs font-medium text-[var(--danger)]">
                    <AlertTriangle size={14} aria-hidden className="mt-0.5 shrink-0" />
                    <div className="min-w-0 [overflow-wrap:anywhere]">
                        {error && <p>{error}</p>}
                        {status.errors.map(message => <p key={message}>{message}</p>)}
                    </div>
                </div>
            )}

            <div className="mt-4 border-t border-[var(--border)] px-4 py-3">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Recent activity</h3>
                {status.recentEvents.length === 0 ? (
                    <p className="py-4 text-center text-sm text-[var(--muted)]">
                        {paused ? "Monitoring is paused." : "Waiting for the first invoice…"}
                    </p>
                ) : (
                    <MonitorEventsGrid events={status.recentEvents} highlightSince={highlightSince} />
                )}
            </div>
        </section>
    )
}

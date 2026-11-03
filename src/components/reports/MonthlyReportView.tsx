import { useEffect, useMemo, useState } from "react"
import { AgGridReact } from "ag-grid-react"
import type { ColDef, GridApi, ICellRendererParams } from "ag-grid-community"
import { FileText, Loader2, RefreshCw, Save } from "lucide-react"
import { fetchMonthlyReport, saveMonthlyReport } from "../../api/client.js"
import type { AlertLevel, FullReport, MonthlyReport } from "../../api/types.js"
import { ALERT_LEVEL_META, formatDateTime, formatMoney } from "../../lib/risk.js"
import { signalLabel } from "../../lib/signals.js"
import GridToolbar from "../grid/GridToolbar.js"
import { setupGrid } from "../grid/gridSetup.js"
import { gridTheme } from "../grid/gridTheme.js"

setupGrid()

const LEVELS: AlertLevel[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

const MONTH = /^\d{4}-(0[1-9]|1[0-2])$/

const currentMonth = () => new Date().toISOString().slice(0, 7)

function Tile({ label, value, warn = false }: { label: string; value: number; warn?: boolean }) {
    return (
        <div className={`rounded-lg px-3 py-2 ${warn ? "bg-[var(--danger-soft)]" : "bg-[var(--bg)]"}`}>
            <dt className="text-xs text-[var(--muted)]">{label}</dt>
            <dd className={`text-xl font-bold tabular-nums ${warn ? "text-[var(--danger)]" : ""}`}>{value}</dd>
        </div>
    )
}

type Row = FullReport["manualReview"][number]

function describe(row: Row): string {
    let money = ""
    if (typeof row.amount === "number") {
        try {
            money = row.currency ? formatMoney(row.amount, row.currency) : String(row.amount)
        } catch {
            money = `${row.amount} ${row.currency ?? ""}`.trim()  // an unknown currency code
        }
    }
    const due = row.dueDate ? `due ${new Date(row.dueDate).toLocaleDateString("en-US", { month: "short", day: "numeric" })}` : ""
    return [row.number && `Invoice #${row.number}`, money, due].filter(Boolean).join(" · ")
}


type GridContext = { onOpenCheck?: (checkId: string) => void }
const RANK: Record<AlertLevel, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 }

function LevelCell({ data }: ICellRendererParams<Row>) {
    if (!data) return null
    const meta = ALERT_LEVEL_META[data.riskLevel]
    return (
        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${meta.soft} ${meta.text}`}>
            <meta.icon size={12} aria-hidden /> {meta.label}
        </span>
    )
}

function ScoreCell({ value }: ICellRendererParams<Row, number>) {
    const score = value ?? 0
    return (
        <span className="flex h-full items-center gap-2">
            <span aria-hidden className="h-1.5 w-12 overflow-hidden rounded-full bg-[var(--border)]">
                <span className="block h-full rounded-full bg-[var(--danger)]" style={{ width: `${Math.min(score, 100)}%` }} />
            </span>
            <span className="tabular-nums">{score}</span>
        </span>
    )
}

function OpenCell({ data, context }: ICellRendererParams<Row, unknown, GridContext>) {
    const open = context.onOpenCheck
    if (!open || !data?.checkId) return null
    const checkId = data.checkId
    return (
        <button
            onClick={() => open(checkId)}
            className="cursor-pointer rounded-md px-2 py-1 text-xs font-semibold text-[var(--primary)] hover:bg-[var(--primary-soft)] focus-visible:outline-2 focus-visible:outline-[var(--primary)]"
        >
            Open check
        </button>
    )
}

const reviewColumns: ColDef<Row>[] = [
    {
        headerName: "Level", field: "riskLevel", width: 112, cellRenderer: LevelCell, filter: "agTextColumnFilter",
        filterValueGetter: p => (p.data ? ALERT_LEVEL_META[p.data.riskLevel].label : ""),
        comparator: (a: AlertLevel, b: AlertLevel) => RANK[a] - RANK[b],
        valueFormatter: p => ALERT_LEVEL_META[p.value as AlertLevel].label,
    },
    { headerName: "Supplier", colId: "supplier", flex: 1, minWidth: 120, filter: "agTextColumnFilter", valueGetter: p => p.data?.supplierName ?? p.data?.invoiceId ?? "" },
    { headerName: "Score", field: "riskScore", width: 110, sort: "desc", filter: "agNumberColumnFilter", cellRenderer: ScoreCell },
    {
        headerName: "Amount", colId: "amount", width: 100, type: "rightAligned", filter: "agNumberColumnFilter",
        valueGetter: p => (typeof p.data?.amount === "number" ? p.data.amount : null),
        valueFormatter: p => (p.data ? (describe(p.data).split(" · ").find(part => !part.startsWith("Invoice #") && !part.startsWith("due ")) ?? "") : ""),
    },
    { headerName: "Due", field: "dueDate", width: 100, valueFormatter: p => (p.value ? new Date(p.value as string).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : "—") },
    { headerName: "Signs", colId: "signs", flex: 1, minWidth: 220, filter: "agTextColumnFilter", valueGetter: p => p.data?.signs.map(signalLabel).join("; ") ?? "" },
    { headerName: "", colId: "open", width: 110, sortable: false, filter: false, cellRenderer: OpenCell, suppressHeaderMenuButton: true },
]

function ManualReviewGrid({ rows, onOpenCheck }: { rows: Row[]; onOpenCheck?: (checkId: string) => void }) {
    const [api, setApi] = useState<GridApi<Row> | null>(null)
    const defaultColDef = useMemo<ColDef<Row>>(() => ({ sortable: true, resizable: true, suppressMovable: true }), [])
    return (
        <>
            <GridToolbar api={api} total={rows.length} exportName="manual-review" label="Filter invoices…" />
            <div className="mt-2 w-full overflow-hidden rounded-lg border border-[var(--border)]" style={{ height: Math.min(300, 34 + 42 * rows.length + 18) }}>
                <AgGridReact<Row>
                    theme={gridTheme}
                    rowData={rows}
                    columnDefs={reviewColumns}
                    defaultColDef={defaultColDef}
                    context={{ onOpenCheck } satisfies GridContext}
                    getRowId={p => p.data.invoiceId}
                    rowHeight={42}
                    headerHeight={34}
                    onGridReady={e => setApi(e.api)}
                />
            </div>
        </>
    )
}

function Body({ report, onOpenCheck }: { report: FullReport; onOpenCheck?: (checkId: string) => void }) {
    const total = Math.max(report.analyses, 1)
    const peak = Math.max(...report.weeklyTrend.map(w => w.analyses), 1)
    return (
        <>
            <dl className="mt-3 grid grid-cols-2 gap-2">
                <Tile label="Checks run" value={report.analyses} />
                <Tile label="Invoices" value={report.invoices} />
                <Tile label="Possible duplicates" value={report.potentialDuplicates} warn={report.potentialDuplicates > 0} />
                <Tile label="Vendor anomalies" value={report.vendorAnomalies} warn={report.vendorAnomalies > 0} />
                <Tile label="Suspicious links" value={report.suspiciousLinks} warn={report.suspiciousLinks > 0} />
            </dl>

            <h3 className="mt-4 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">By risk level</h3>
            <ul className="mt-2 flex flex-col gap-1.5">
                {LEVELS.map(level => {
                    const meta = ALERT_LEVEL_META[level]
                    const count = report.byLevel[level] ?? 0
                    return (
                        <li key={level} className="flex items-center gap-2 text-xs">
                            <span className="w-14 shrink-0">{level.charAt(0) + level.slice(1).toLowerCase()}</span>
                            <span className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--border)]">
                                <span className={`block h-full rounded-full ${meta.solid}`} style={{ width: `${(count / total) * 100}%` }} />
                            </span>
                            <span className="w-6 shrink-0 text-right tabular-nums">{count}</span>
                        </li>
                    )
                })}
            </ul>

            {report.weeklyTrend.length > 0 && (
                <>
                    <h3 className="mt-4 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Weekly trend</h3>
                    <ul className="mt-2 flex flex-col gap-1.5">
                        {report.weeklyTrend.map(week => (
                            <li key={week.weekStart} className="flex items-center gap-2 text-xs">
                                <time dateTime={week.weekStart} className="w-14 shrink-0 text-[var(--muted)]">
                                    {new Date(week.weekStart).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                                </time>
                                <span className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--border)]">
                                    <span className="block h-full rounded-full bg-[var(--primary)]" style={{ width: `${(week.analyses / peak) * 100}%` }} />
                                </span>
                                <span className="w-24 shrink-0 text-right tabular-nums text-[var(--muted)]">
                                    {week.analyses} checks, {week.highOrCritical} high+
                                </span>
                            </li>
                        ))}
                    </ul>
                </>
            )}

            {report.topFlaggedSuppliers.length > 0 && (
                <>
                    <h3 className="mt-4 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Most flagged senders</h3>
                    <ul className="mt-2 flex flex-col gap-1.5">
                        {report.topFlaggedSuppliers.map(s => (
                            <li key={s.supplierEmail} className="flex items-baseline justify-between gap-2 rounded-lg bg-[var(--bg)] px-3 py-2 text-xs">
                                <span className="min-w-0 [overflow-wrap:anywhere]">
                                    <span className="font-semibold">{s.supplierName ?? "Unknown name"}</span>
                                    <span className="block text-[var(--muted)]">{s.supplierEmail}</span>
                                </span>
                                <span className="shrink-0 tabular-nums">{s.flaggedInvoices} flagged</span>
                            </li>
                        ))}
                    </ul>
                </>
            )}

            {report.manualReview.length > 0 && (
                <>
                    <h3 className="mt-4 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Worth a manual look</h3>
                    <ManualReviewGrid rows={report.manualReview} onOpenCheck={onOpenCheck} />
                </>
            )}
        </>
    )
}

export default function MonthlyReportView({ onOpenCheck }: { onOpenCheck?: (checkId: string) => void }) {
    const [month, setMonth] = useState(currentMonth)
    const [report, setReport] = useState<MonthlyReport | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [busy, setBusy] = useState<"load" | "save" | null>("load")
    const [reloadKey, setReloadKey] = useState(0)

    useEffect(() => {
        if (!MONTH.test(month)) return  // a half-typed month is not asked for
        let cancelled = false
        fetchMonthlyReport(month)
            .then(next => { if (!cancelled) { setReport(next); setError(null) } })
            .catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : "Could not load the report.") })
            .finally(() => { if (!cancelled) setBusy(null) })
        return () => { cancelled = true }
    }, [month, reloadKey])

    const save = async () => {
        setBusy("save")
        try {
            setReport(await saveMonthlyReport(month))
            setError(null)
        } catch (e) {
            setError(e instanceof Error ? e.message : "Could not save the report.")
        } finally {
            setBusy(null)
        }
    }

    const button = "inline-flex min-h-8 flex-1 cursor-pointer items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"

    return (
        <section aria-label="Monthly report" className="p-3">
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm">
                <header className="flex items-center gap-3">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--primary-soft)] text-[var(--primary)]">
                        <FileText size={18} aria-hidden />
                    </span>
                    <div className="min-w-0 flex-1">
                        <h2 className="text-sm font-bold leading-tight">Monthly report</h2>
                        <p className="truncate text-xs text-[var(--muted)]">
                            {report?.saved ? `Saved v${report.version ?? 1}${report.createdAt ? `, ${formatDateTime(report.createdAt)}` : ""}` : "Not saved yet"}
                        </p>
                    </div>
                    <input
                        type="month"
                        aria-label="Report month"
                        value={month}
                        max={currentMonth()}
                        onChange={e => { if (MONTH.test(e.target.value)) setBusy("load"); setMonth(e.target.value) }}
                        className="w-32 shrink-0 rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-xs focus-visible:outline-2 focus-visible:outline-[var(--primary)]"
                    />
                </header>

                <div className="mt-3 flex gap-2">
                    <button className={`${button} border border-[var(--border)] hover:bg-[var(--primary-soft)]`} disabled={busy !== null} onClick={() => { setBusy("load"); setReloadKey(k => k + 1) }}>
                        {busy === "load" ? <Loader2 size={14} aria-hidden className="motion-safe:animate-spin" /> : <RefreshCw size={14} aria-hidden />} Refresh
                    </button>
                    <button className={`${button} bg-[var(--primary)] text-white hover:opacity-90`} disabled={busy !== null} onClick={() => void save()}>
                        {busy === "save" ? <Loader2 size={14} aria-hidden className="motion-safe:animate-spin" /> : <Save size={14} aria-hidden />} Save version
                    </button>
                </div>

                {error && <p role="alert" className="mt-3 rounded-lg bg-[var(--danger-soft)] px-3 py-2 text-xs font-medium text-[var(--danger)]">{error}</p>}

                {!report && !error && <p role="status" className="p-8 text-center text-sm text-[var(--muted)]">Loading report…</p>}

                {report?.empty && <p className="p-6 text-center text-sm text-[var(--muted)]">{report.message}</p>}

                {report && !report.empty && <Body report={report} onOpenCheck={onOpenCheck} />}

                {report && <p className="mt-4 text-[11px] leading-snug text-[var(--muted)]">{report.wording}</p>}
            </div>
        </section>
    )
}

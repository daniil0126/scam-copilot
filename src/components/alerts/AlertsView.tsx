import { useCallback, useEffect, useMemo, useState } from "react"
import { AgGridReact } from "ag-grid-react"
import type { ColDef, GridApi, ICellRendererParams } from "ag-grid-community"
import { BellOff, Loader2 } from "lucide-react"
import { fetchNotifications, markNotificationRead } from "../../api/client.js"
import type { AppNotification } from "../../api/types.js"
import { ALERT_LEVEL_META, formatDateTime, formatMoney } from "../../lib/risk.js"
import { signalLabel } from "../../lib/signals.js"
import GridToolbar from "../grid/GridToolbar.js"
import { setupGrid } from "../grid/gridSetup.js"
import { gridTheme } from "../grid/gridTheme.js"

setupGrid()

const PAGE = 20

type Props = {
    // Changes when the unread count does, so a new alert appears without a click.
    reloadKey: number
    onRead: () => void
    // Opens that stored check in History.
    onOpenCheck: (checkId: string) => void
}

function describe(item: AppNotification): string {
    const invoice = item.invoice
    if (!invoice) return "Details unavailable"
    let money = ""
    if (invoice.amount !== null) {
        try {
            money = invoice.currency ? formatMoney(invoice.amount, invoice.currency) : String(invoice.amount)
        } catch {
            money = `${invoice.amount} ${invoice.currency ?? ""}`.trim()  // an unknown currency code
        }
    }
    return [invoice.supplierName ?? "Unknown sender", invoice.number && `#${invoice.number}`, money].filter(Boolean).join(" · ")
}


const RANK: Record<AppNotification["riskLevel"], number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 }

function LevelCell({ data }: ICellRendererParams<AppNotification>) {
    if (!data) return null
    const risk = ALERT_LEVEL_META[data.riskLevel]
    return (
        <span className="inline-flex items-center gap-1.5">
            <span aria-label={data.read ? undefined : "Unread"} className={`h-2 w-2 shrink-0 rounded-full ${data.read ? "" : "bg-[var(--primary)]"}`} />
            <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${risk.soft} ${risk.text}`}>
                <risk.icon size={12} aria-hidden /> {risk.label}
            </span>
        </span>
    )
}

const columnDefs: ColDef<AppNotification>[] = [
    {
        headerName: "Level", field: "riskLevel", width: 150, cellRenderer: LevelCell, filter: "agTextColumnFilter",
        filterValueGetter: p => (p.data ? ALERT_LEVEL_META[p.data.riskLevel].label : ""),
        comparator: (a: AppNotification["riskLevel"], b: AppNotification["riskLevel"]) => RANK[a] - RANK[b],
        valueFormatter: p => ALERT_LEVEL_META[p.value as AppNotification["riskLevel"]].label,
    },
    { headerName: "Supplier", colId: "supplier", flex: 1, minWidth: 120, filter: "agTextColumnFilter", valueGetter: p => p.data?.invoice?.supplierName ?? "Unknown sender", tooltipValueGetter: p => p.data?.title ?? "" },
    {
        headerName: "Amount", colId: "amount", width: 100, type: "rightAligned", filter: "agNumberColumnFilter",
        valueGetter: p => p.data?.invoice?.amount ?? null,
        valueFormatter: p => (p.data?.invoice ? describe(p.data).split(" · ").at(-1) ?? "" : ""),
    },
    { headerName: "Detected", field: "detectedAt", width: 150, sort: "desc", valueFormatter: p => formatDateTime(p.value as string) },
    { headerName: "Signs", colId: "signals", flex: 1, minWidth: 220, filter: "agTextColumnFilter", valueGetter: p => p.data?.signals.map(signalLabel).join("; ") ?? "" },
]

export default function AlertsView({ reloadKey, onRead, onOpenCheck }: Props) {
    const [items, setItems] = useState<AppNotification[] | null>(null)
    const [nextCursor, setNextCursor] = useState<string | null>(null)
    const [unreadOnly, setUnreadOnly] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [loadingMore, setLoadingMore] = useState(false)
    const [openId, setOpenId] = useState<string | null>(null)
    const [api, setApi] = useState<GridApi<AppNotification> | null>(null)
    const defaultColDef = useMemo<ColDef<AppNotification>>(() => ({ sortable: true, resizable: true, suppressMovable: true }), [])

    useEffect(() => {
        let cancelled = false
        fetchNotifications({ unreadOnly, limit: PAGE })
            .then(page => {
                if (cancelled) return
                setItems(page.items)
                setNextCursor(page.nextCursor)
                setError(null)
                // The list is on screen, so what it shows is seen. The badge drops, which reloads the list with the rows as read.
                const unseen = page.items.filter(n => !n.read)
                if (unseen.length) {
                    void Promise.all(unseen.map(n => markNotificationRead(n.id))).then(onRead).catch(() => { /* stays unread */ })
                }
            })
            .catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : "Could not load alerts.") })
        return () => { cancelled = true }
    }, [unreadOnly, reloadKey]) // eslint-disable-line react-hooks/exhaustive-deps, react-x/exhaustive-deps -- onRead only refreshes the badge

    const loadMore = async () => {
        if (!nextCursor) return
        setLoadingMore(true)
        try {
            const page = await fetchNotifications({ unreadOnly, limit: PAGE, cursor: nextCursor })
            setItems(current => [...(current ?? []), ...page.items])
            setNextCursor(page.nextCursor)
        } catch (e) {
            setError(e instanceof Error ? e.message : "Could not load more alerts.")
        } finally {
            setLoadingMore(false)
        }
    }

    // Opening an unread alert marks it read. The row changes at once and goes back if the server refuses.
    const open = useCallback(async (item: AppNotification) => {
        setOpenId(id => (id === item.id ? null : item.id))
        if (item.read) return
        setItems(current => current?.map(n => (n.id === item.id ? { ...n, read: true } : n)) ?? null)
        try {
            await markNotificationRead(item.id)
            onRead()
        } catch (e) {
            setItems(current => current?.map(n => (n.id === item.id ? { ...n, read: false } : n)) ?? null)
            setError(e instanceof Error ? e.message : "Could not mark the alert as read.")
        }
    }, [onRead])

    const selected = items?.find(n => n.id === openId) ?? null

    return (
        <section aria-label="Alerts" className="p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
                <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Alerts</h2>
                <label className="flex cursor-pointer items-center gap-1.5 text-xs text-[var(--muted)]">
                    <input type="checkbox" checked={unreadOnly} onChange={e => { setItems(null); setUnreadOnly(e.target.checked) }} />
                    Unread only
                </label>
            </div>

            {error && <p role="alert" className="mb-2 rounded-lg bg-[var(--danger-soft)] px-3 py-2 text-xs font-medium text-[var(--danger)]">{error}</p>}

            {!items && !error && (
                <div role="status" className="flex items-center justify-center gap-2 p-10 text-sm text-[var(--muted)]">
                    <Loader2 size={18} aria-hidden className="motion-safe:animate-spin" /> Loading alerts…
                </div>
            )}

            {items && items.length === 0 && (
                <div className="flex flex-col items-center gap-2 p-10 text-center text-sm text-[var(--muted)]">
                    <BellOff size={28} aria-hidden />
                    {unreadOnly ? "No unread alerts." : "No alerts yet. An alert appears when a checked invoice shows signs worth a look."}
                </div>
            )}

            {items && items.length > 0 && (
                <>
                    <GridToolbar api={api} total={items.length} exportName="alerts" label="Filter alerts…" />
                    <div className="mt-2 w-full overflow-hidden rounded-lg border border-[var(--border)] [&_.ag-row]:cursor-pointer" style={{ height: Math.min(300, 34 + 42 * items.length + 18) }}>
                        <AgGridReact<AppNotification>
                            theme={gridTheme}
                            rowData={items}
                            columnDefs={columnDefs}
                            defaultColDef={defaultColDef}
                            getRowId={p => p.data.id}
                            rowHeight={42}
                            headerHeight={34}
                            tooltipShowDelay={400}
                            rowClassRules={{ "font-bold": p => !!p.data && !p.data.read }}
                            onGridReady={e => setApi(e.api)}
                            onRowClicked={e => { if (e.data) void open(e.data) }}
                            onCellKeyDown={e => {
                                const key = (e.event as KeyboardEvent | null)?.key
                                if (e.data && (key === "Enter" || key === " ")) void open(e.data)
                            }}
                        />
                    </div>
                    {selected && (
                        <div className="mt-2 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2.5 text-xs leading-snug">
                            <p className="font-semibold [overflow-wrap:anywhere]">{selected.title}</p>
                            <p className="mt-1 text-[var(--muted)] [overflow-wrap:anywhere]">{describe(selected)}</p>
                            <p className="mt-1 [overflow-wrap:anywhere]">{selected.message}</p>
                            {selected.invoice ? (
                                <button
                                    onClick={() => onOpenCheck(selected.invoice!.checkId)}
                                    className="mt-2 min-h-8 cursor-pointer rounded-lg border border-[var(--border)] px-3 text-xs font-semibold text-[var(--primary)] hover:bg-[var(--primary-soft)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"
                                >
                                    Open this check
                                </button>
                            ) : (
                                <p className="mt-2 text-[var(--muted)] [overflow-wrap:anywhere]">
                                    No stored check for this invoice (PayPal id {selected.invoiceId}). If the backend was updated, restart it.
                                </p>
                            )}
                        </div>
                    )}
                </>
            )}

            {nextCursor && (
                <button
                    onClick={() => void loadMore()}
                    disabled={loadingMore}
                    className="mt-2 inline-flex min-h-8 w-full cursor-pointer items-center justify-center gap-1.5 rounded-lg text-xs font-semibold text-[var(--primary)] hover:bg-[var(--primary-soft)] disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"
                >
                    {loadingMore && <Loader2 size={14} aria-hidden className="motion-safe:animate-spin" />} Load more
                </button>
            )}
        </section>
    )
}

import { useEffect, useMemo, useRef, useState } from "react"
import { AgGridReact } from "ag-grid-react"
import type { ColDef, GridApi, GridReadyEvent, ICellRendererParams } from "ag-grid-community"
import type { MonitoringEvent, RiskLevel } from "../../api/types.js"
import { LEVEL_META } from "../../lib/risk.js"
import GridToolbar from "../grid/GridToolbar.js"
import { setupGrid } from "../grid/gridSetup.js"
import { gridTheme } from "../grid/gridTheme.js"
import { eventKey, money } from "./monitoringMeta.js"

setupGrid()

const RANK: Record<RiskLevel, number> = { high: 3, medium: 2, low: 1 }
const reducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false

function RiskCell({ value }: ICellRendererParams<MonitoringEvent, RiskLevel | null>) {
    if (!value) return <span className="text-[var(--muted)]">—</span>
    const meta = LEVEL_META[value]
    return (
        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${meta.soft} ${meta.text}`}>
            <meta.icon size={12} aria-hidden /> {meta.label}
        </span>
    )
}

const clock = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })

const columnDefs: ColDef<MonitoringEvent>[] = [
    {
        headerName: "Risk", field: "riskLevel", width: 120, cellRenderer: RiskCell,
        filter: "agTextColumnFilter",
        filterValueGetter: p => (p.data?.riskLevel ? LEVEL_META[p.data.riskLevel].label : ""),
        comparator: (a: RiskLevel | null, b: RiskLevel | null) => (a ? RANK[a] : 0) - (b ? RANK[b] : 0),
        valueFormatter: p => (p.value ? LEVEL_META[p.value as RiskLevel].label : ""),
    },
    { headerName: "Supplier", field: "senderName", flex: 1, minWidth: 110, filter: "agTextColumnFilter", valueFormatter: p => (p.value as string | null) ?? "Unknown sender", tooltipField: "senderName" },
    {
        headerName: "Amount", colId: "amount", width: 96, type: "rightAligned", filter: "agNumberColumnFilter",
        valueGetter: p => (p.data?.amount == null || Number.isNaN(Number(p.data.amount)) ? null : Number(p.data.amount)),
        valueFormatter: p => money(p.data?.amount ?? null, p.data?.currency ?? null),
    },
    { headerName: "Event", field: "eventType", width: 112, hide: true, filter: "agTextColumnFilter", valueFormatter: p => (p.value === "NEW_INVOICE" ? "New invoice" : "Updated") },
    { headerName: "Detected", field: "detectedAt", width: 92, sort: "desc", valueFormatter: p => (p.value ? clock(p.value as string) : "") },
    { headerName: "#", field: "invoiceNumber", width: 76, hide: true, filter: "agTextColumnFilter", valueFormatter: p => (p.value as string | null) ?? "—" },
    {
        headerName: "Signs", colId: "signals", flex: 1, minWidth: 220, filter: "agTextColumnFilter",
        valueGetter: p => p.data?.signals.join("; ") ?? "",
        tooltipValueGetter: p => p.data?.signals.join("\n") ?? "",
    },
]

// The latest events of the monitor as an AG Grid table. New events are added to the grid with a transaction, not by
// rebuilding the data, so the table keeps its sorting, filter and scroll position while it fills by itself.
export default function MonitorEventsGrid({ events, highlightSince }: { events: MonitoringEvent[]; highlightSince: string }) {
    const [api, setApi] = useState<GridApi<MonitoringEvent> | null>(null)
    const known = useRef(new Map<string, string>())  // row id -> serialized row, to tell a changed row from a same one
    const since = useRef(highlightSince)
    useEffect(() => { since.current = highlightSince }, [highlightSince])

    useEffect(() => {
        const grid = api
        if (!grid) return
        const next = new Map(events.map(e => [eventKey(e), e]))
        const add: MonitoringEvent[] = []
        const update: MonitoringEvent[] = []
        const remove: MonitoringEvent[] = []
        for (const [id, e] of next) {
            const serialized = JSON.stringify(e)
            if (!known.current.has(id)) add.push(e)
            else if (known.current.get(id) !== serialized) update.push(e)
            known.current.set(id, serialized)
        }
        grid.forEachNode(node => { if (node.data && !next.has(eventKey(node.data))) { remove.push(node.data); known.current.delete(eventKey(node.data)) } })
        const first = known.current.size === next.size && add.length === next.size
        const result = grid.applyTransaction({ add, update, remove, addIndex: 0 })
        if (!first && result?.add.length && !reducedMotion()) grid.flashCells({ rowNodes: result.add, flashDuration: 1200, fadeDuration: 1500 })
    }, [events, api])

    const onReady = (e: GridReadyEvent<MonitoringEvent>) => setApi(e.api)
    const defaultColDef = useMemo<ColDef<MonitoringEvent>>(() => ({ sortable: true, resizable: true, suppressMovable: true }), [])

    return (
        <div>
            <GridToolbar api={api} total={events.length} exportName="monitor-events" label="Filter events…" />
            <div className="mt-2 h-[300px] w-full overflow-hidden rounded-lg border border-[var(--border)]">
                <AgGridReact<MonitoringEvent>
                    theme={gridTheme}
                    columnDefs={columnDefs}
                    defaultColDef={defaultColDef}
                    getRowId={p => eventKey(p.data)}
                    rowHeight={42}
                    headerHeight={34}
                    tooltipShowDelay={400}
                    animateRows={!reducedMotion()}
                    rowClassRules={{ "sc-fresh": p => !!p.data && Date.parse(p.data.detectedAt) > Date.parse(since.current) }}
                    onGridReady={onReady}
                    noRowsOverlayComponent={() => <span className="text-sm text-[var(--muted)]">No events match the filter.</span>}
                />
            </div>
        </div>
    )
}

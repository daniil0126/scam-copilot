import { useEffect, useMemo, useRef, useState } from "react"
import { AgGridReact } from "ag-grid-react"
import {
    AllCommunityModule,
    ColDef,
    ICellRendererParams,
    ModuleRegistry,
    colorSchemeDark,
    colorSchemeLight,
    themeQuartz,
} from "ag-grid-community"
import { ArrowUpDown, Check, ChevronRight, Filter } from "lucide-react"
import type { HistoryEntry, RiskLevel, UserSettings } from "../../types.js"
import { LEVEL_META, formatDateTime, formatMoney } from "../../lib/risk.js"

ModuleRegistry.registerModules([AllCommunityModule])

type SortMode = "date-desc" | "price-desc" | "price-asc"
type OpenMenu = "filter" | "sort" | null

const RISK_LEVELS: RiskLevel[] = ["high", "medium", "low"]

const SORT_OPTIONS: { value: SortMode; label: string }[] = [
    { value: "date-desc", label: "Date (newest)" },
    { value: "price-desc", label: "Price: highest first" },
    { value: "price-asc", label: "Price: lowest first" },
]

const COMPARATORS: Record<SortMode, (a: HistoryEntry, b: HistoryEntry) => number> = {
    "date-desc": (a, b) => new Date(b.checkedAt).getTime() - new Date(a.checkedAt).getTime(),
    "price-desc": (a, b) => b.invoice.amount - a.invoice.amount,
    "price-asc": (a, b) => a.invoice.amount - b.invoice.amount,
}

const TRIGGER_CLASS =
    "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-[var(--border)] bg-[var(--card)] text-[var(--text)] shadow-sm hover:bg-[var(--primary-soft)] transition-colors"

const lightTheme = themeQuartz.withPart(colorSchemeLight)
const darkTheme = themeQuartz.withPart(colorSchemeDark)

const ROW_STYLE = { cursor: "pointer" }

function LevelCell({ data }: ICellRendererParams<HistoryEntry>) {
    if (!data) return null
    const meta = LEVEL_META[data.level]
    const Icon = meta.icon
    return (
        <div className="flex items-center h-full">
            <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${meta.soft} ${meta.text}`}>
                <Icon size={18} aria-hidden />
            </span>
        </div>
    )
}

function SupplierCell({ data }: ICellRendererParams<HistoryEntry>) {
    if (!data) return null
    return (
        <div className="flex flex-col justify-center h-full py-1">
            <span className="block truncate text-sm font-semibold text-[var(--text)]">
                {data.invoice.supplier.name}
            </span>
            <span className="block text-xs text-[var(--muted)]">{formatDateTime(data.checkedAt)}</span>
        </div>
    )
}

function AmountCell({ data }: ICellRendererParams<HistoryEntry>) {
    if (!data) return null
    const meta = LEVEL_META[data.level]
    return (
        <div className="flex flex-col justify-center items-end h-full py-1">
            <span className="block text-sm font-semibold">
                {formatMoney(data.invoice.amount, data.invoice.currency)}
            </span>
            <span className={`block text-xs font-medium ${meta.text}`}>{meta.label}</span>
        </div>
    )
}

function ChevronCell() {
    return (
        <div className="flex items-center justify-end h-full">
            <ChevronRight size={16} className="text-[var(--muted)]" aria-hidden />
        </div>
    )
}

const columnDefs: ColDef<HistoryEntry>[] = [
    { width: 70, pinned: "left", cellRenderer: LevelCell },
    { headerName: "Description", flex: 2, minWidth: 200, cellRenderer: SupplierCell },
    { headerName: "Amount", flex: 1.5, minWidth: 140, cellRenderer: AmountCell },
    { width: 50, pinned: "right", cellRenderer: ChevronCell },
]

interface HistoryGridProps {
    data: HistoryEntry[]
    settings: UserSettings
    onOpen: (id: string) => void
}

export default function HistoryGrid({ data, settings, onOpen }: HistoryGridProps) {
    const [riskFilters, setRiskFilters] = useState<Record<RiskLevel, boolean>>({
        high: true,
        medium: true,
        low: true,
    })
    const [sortMode, setSortMode] = useState<SortMode>("date-desc")
    const [openMenu, setOpenMenu] = useState<OpenMenu>(null)
    const toolbarRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (!openMenu) return

        function handleMouseDown(event: MouseEvent) {
            if (toolbarRef.current && !toolbarRef.current.contains(event.target as Node)) {
                setOpenMenu(null)
            }
        }
        function handleKeyDown(event: KeyboardEvent) {
            if (event.key === "Escape") setOpenMenu(null)
        }

        document.addEventListener("mousedown", handleMouseDown)
        document.addEventListener("keydown", handleKeyDown)
        return () => {
            document.removeEventListener("mousedown", handleMouseDown)
            document.removeEventListener("keydown", handleKeyDown)
        }
    }, [openMenu])

    const rows = useMemo(
        () => data.filter(entry => riskFilters[entry.level]).sort(COMPARATORS[sortMode]),
        [data, riskFilters, sortMode]
    )

    const toggleMenu = (menu: Exclude<OpenMenu, null>) =>
        setOpenMenu(current => (current === menu ? null : menu))

    const toggleLevel = (level: RiskLevel) =>
        setRiskFilters(prev => ({ ...prev, [level]: !prev[level] }))

    return (
        <div className="flex flex-col gap-3 w-full">
            <div ref={toolbarRef} className="flex justify-end gap-2 px-4 pt-2 relative z-20">
                <div className="relative">
                    <button
                        onClick={() => toggleMenu("filter")}
                        aria-haspopup="true"
                        aria-expanded={openMenu === "filter"}
                        className={TRIGGER_CLASS}
                    >
                        <Filter size={14} aria-hidden /> Filter
                    </button>

                    {openMenu === "filter" && (
                        <div className="absolute right-0 mt-2 w-48 bg-[var(--card)] border border-[var(--border)] rounded-xl shadow-lg p-3 z-30 flex flex-col gap-2">
                            <span className="text-xs font-semibold text-[var(--muted)] px-1">Risk level</span>
                            {RISK_LEVELS.map(level => (
                                <label
                                    key={level}
                                    className={`flex items-center gap-2 text-xs font-semibold cursor-pointer px-1 py-1 hover:bg-[var(--primary-soft)] rounded ${LEVEL_META[level].text}`}
                                >
                                    <input
                                        type="checkbox"
                                        checked={riskFilters[level]}
                                        onChange={() => toggleLevel(level)}
                                        className="accent-current"
                                    />
                                    {LEVEL_META[level].label}
                                </label>
                            ))}
                        </div>
                    )}
                </div>

                <div className="relative">
                    <button
                        onClick={() => toggleMenu("sort")}
                        aria-haspopup="true"
                        aria-expanded={openMenu === "sort"}
                        className={TRIGGER_CLASS}
                    >
                        <ArrowUpDown size={14} aria-hidden /> Sort
                    </button>

                    {openMenu === "sort" && (
                        <div className="absolute right-0 mt-2 w-52 bg-[var(--card)] border border-[var(--border)] rounded-xl shadow-lg p-2 z-30 flex flex-col gap-1">
                            <span className="text-xs font-semibold text-[var(--muted)] px-2 py-1">Sort by</span>
                            {SORT_OPTIONS.map(option => (
                                <button
                                    key={option.value}
                                    onClick={() => {
                                        setSortMode(option.value)
                                        setOpenMenu(null)
                                    }}
                                    className={`flex items-center justify-between w-full text-left text-xs px-2 py-1.5 rounded hover:bg-[var(--primary-soft)] ${
                                        sortMode === option.value ? "font-bold text-[var(--primary)]" : "text-[var(--text)]"
                                    }`}
                                >
                                    {option.label}
                                    {sortMode === option.value && <Check size={14} aria-hidden />}
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {rows.length === 0 ? (
                <div className="flex h-[420px] w-full items-center justify-center rounded-xl border border-[var(--border)] bg-[var(--card)] text-sm text-[var(--muted)]">
                    No results for selected filters.
                </div>
            ) : (
                <div className="w-full h-[420px] rounded-xl overflow-hidden border border-[var(--border)] shadow-sm">
                    <AgGridReact<HistoryEntry>
                        theme={settings.theme === "dark" ? darkTheme : lightTheme}
                        rowData={rows}
                        columnDefs={columnDefs}
                        getRowId={params => params.data.id}
                        rowHeight={64}
                        headerHeight={0}
                        rowStyle={ROW_STYLE}
                        suppressCellFocus
                        onRowClicked={event => {
                            if (event.data) onOpen(event.data.id)
                        }}
                    />
                </div>
            )}
        </div>
    )
}
import { useEffect, useMemo, useRef, useState } from "react"
import { AgGridReact } from "ag-grid-react"
import {
    ClientSideRowModelModule,
    ModuleRegistry,
    colorSchemeDark,
    colorSchemeLight,
    themeQuartz,
    type ColDef,
    type ICellRendererParams,
} from "ag-grid-community"
import { ArrowDownUp, Check, ChevronRight, Filter, Search } from "lucide-react"
import type { HistoryEntry, RiskLevel, UserSettings } from "../../api/types.js"
import { LEVEL_META, formatDateTime, formatMoney } from "../../lib/risk.js"

// Rejestracja lżejszego modułu AG Grid
ModuleRegistry.registerModules([ClientSideRowModelModule])

type SortMode = "date-desc" | "price-desc" | "price-asc"

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

const gridParams = {
    backgroundColor: "transparent",
    headerBackgroundColor: "transparent",
    borderColor: "transparent",
    wrapperBorder: false,
    wrapperBorderRadius: 0,
    rowBorder: { style: "solid", width: 1, color: "var(--border)" },
} as const

const lightTheme = themeQuartz.withPart(colorSchemeLight).withParams(gridParams)
const darkTheme = themeQuartz.withPart(colorSchemeDark).withParams(gridParams)

// Poprawione formatowanie kwoty w statystykach na styl angielski (np. $2.5k)
function computeStats(data: HistoryEntry[]) {
    let highRiskCount = 0
    let flaggedSum = 0

    for (const entry of data) {
        if (entry.level !== "high") continue
        highRiskCount++
        flaggedSum += entry.invoice.amount
    }

    const formattedFlagged = flaggedSum >= 1000 
        ? `$${(flaggedSum / 1000).toFixed(1)}k` 
        : `$${flaggedSum.toFixed(2)}`

    return {
        totalChecked: data.length,
        highRiskCount,
        flaggedAmount: formattedFlagged,
    }
}

function LevelCell({ data }: ICellRendererParams<HistoryEntry>) {
    if (!data) return null
    const meta = LEVEL_META[data.level]
    const Icon = meta.icon
    return (
        <div className="flex items-center justify-center h-full">
            <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${meta.soft} ${meta.text}`}>
                <Icon size={18} aria-hidden />
            </span>
        </div>
    )
}

function SupplierCell({ data }: ICellRendererParams<HistoryEntry>) {
    if (!data) return null
    return (
        <div className="flex flex-col justify-center h-full py-1 min-w-0 pr-2">
            <span className="block truncate text-sm font-semibold text-[var(--text)]">
                {data.invoice.supplier.name}
            </span>
            <span className="block truncate text-xs text-[var(--muted)]">
                {formatDateTime(data.checkedAt)}
            </span>
        </div>
    )
}

function AmountCell({ data }: ICellRendererParams<HistoryEntry>) {
    if (!data) return null
    const meta = LEVEL_META[data.level]
    return (
        <div className="flex flex-col justify-center items-end h-full py-1 text-right">
            <span className="block whitespace-nowrap text-sm font-semibold text-[var(--text)]">
                {formatMoney(data.invoice.amount, data.invoice.currency)}
            </span>
            <span className={`block whitespace-nowrap text-xs font-medium ${meta.text}`}>
                {meta.label}
            </span>
        </div>
    )
}

function ChevronCell() {
    return (
        <div className="flex items-center justify-center h-full pr-1">
            {/* Poprawiona, widoczna strzałka */}
            <ChevronRight size={22} strokeWidth={2.5} className="w-5 h-5 shrink-0 text-[var(--muted)]" aria-hidden />
        </div>
    )
}

const columnDefs: ColDef<HistoryEntry>[] = [
    { width: 60, minWidth: 60, maxWidth: 60, pinned: "left", cellRenderer: LevelCell },
    { flex: 2, minWidth: 130, cellRenderer: SupplierCell },
    { flex: 1.2, minWidth: 100, cellRenderer: AmountCell },
    { width: 48, minWidth: 48, maxWidth: 48, pinned: "right", cellRenderer: ChevronCell },
]

interface HistoryItemProps {
    data: HistoryEntry[]
    settings: UserSettings
    onOpen: (id: string) => void
}

export default function HistoryItem({ data, settings, onOpen }: HistoryItemProps) {
    const [searchQuery, setSearchQuery] = useState("")
    const [riskFilters, setRiskFilters] = useState<Record<RiskLevel, boolean>>({
        high: true,
        medium: true,
        low: true,
    })
    const [sortMode, setSortMode] = useState<SortMode>("date-desc")
    const [isMenuOpen, setIsMenuOpen] = useState(false)
    const menuRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (!isMenuOpen) return

        function handleMouseDown(event: MouseEvent) {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setIsMenuOpen(false)
            }
        }
        function handleKeyDown(event: KeyboardEvent) {
            if (event.key === "Escape") setIsMenuOpen(false)
        }

        document.addEventListener("mousedown", handleMouseDown)
        document.addEventListener("keydown", handleKeyDown)
        return () => {
            document.removeEventListener("mousedown", handleMouseDown)
            document.removeEventListener("keydown", handleKeyDown)
        }
    }, [isMenuOpen])

    const stats = useMemo(() => computeStats(data), [data])

    const rows = useMemo(() => {
        const query = searchQuery.trim().toLowerCase()
        return data
            .filter(
                entry =>
                    riskFilters[entry.level] &&
                    entry.invoice.supplier.name.toLowerCase().includes(query)
            )
            .sort(COMPARATORS[sortMode])
    }, [data, searchQuery, riskFilters, sortMode])

    const toggleLevel = (level: RiskLevel) =>
        setRiskFilters(prev => ({ ...prev, [level]: !prev[level] }))

    return (
        <div className="flex flex-col gap-4 p-4 w-full box-border">
            <div className="grid grid-cols-3 gap-2 py-2 border-b border-[var(--border)] text-center">
                <div>
                    <span className="block text-xs text-[var(--muted)]">Invoices checked</span>
                    <span className="text-xl font-bold text-[var(--text)]">{stats.totalChecked}</span>
                </div>
                <div>
                    <span className="block text-xs text-[var(--muted)]">High risk</span>
                    <span className={`text-xl font-bold ${LEVEL_META.high.text}`}>{stats.highRiskCount}</span>
                </div>
                <div>
                    <span className="block text-xs text-[var(--muted)]">Flagged amount</span>
                    <span className="text-xl font-bold text-[var(--text)]">{stats.flaggedAmount}</span>
                </div>
            </div>

            <div className="flex flex-col gap-2">
                <h3 className="text-sm font-semibold text-[var(--text)]">Invoice audit log</h3>

                <div className="flex items-center gap-2">
                    <div className="relative flex-1 min-w-0">
                        <Search
                            size={16}
                            className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]"
                            aria-hidden
                        />
                        <input
                            type="search"
                            aria-label="Search supplier"
                            placeholder="Search supplier..."
                            value={searchQuery}
                            onChange={e => setSearchQuery(e.target.value)}
                            className="w-full pl-9 pr-3 py-2 text-sm bg-[var(--card)] text-[var(--text)] border border-[var(--border)] rounded-xl focus:outline-none focus:ring-2 focus:ring-[var(--primary)] transition-colors shadow-sm"
                        />
                    </div>

                    <div className="relative shrink-0" ref={menuRef}>
                        <button
                            onClick={() => setIsMenuOpen(open => !open)}
                            aria-haspopup="true"
                            aria-expanded={isMenuOpen}
                            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-xl border border-[var(--border)] bg-[var(--card)] text-[var(--text)] shadow-sm hover:bg-[var(--primary-soft)] transition-colors"
                        >
                            <Filter size={16} aria-hidden /> Filters
                        </button>

                        {isMenuOpen && (
                            <div className="absolute right-0 mt-2 w-56 bg-[var(--card)] border border-[var(--border)] rounded-xl shadow-xl p-3 z-30 flex flex-col gap-3">
                                <div className="flex flex-col gap-1.5">
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

                                <hr className="border-[var(--border)]" />

                                <div className="flex flex-col gap-1">
                                    <span className="flex items-center gap-1 text-xs font-semibold text-[var(--muted)] px-1">
                                        <ArrowDownUp size={12} aria-hidden /> Sort by
                                    </span>
                                    {SORT_OPTIONS.map(option => (
                                        <button
                                            key={option.value}
                                            onClick={() => setSortMode(option.value)}
                                            className={`flex items-center justify-between w-full text-left text-xs px-2 py-1.5 rounded hover:bg-[var(--primary-soft)] ${
                                                sortMode === option.value
                                                    ? "font-bold text-[var(--primary)]"
                                                    : "text-[var(--text)]"
                                            }`}
                                        >
                                            {option.label}
                                            {sortMode === option.value && <Check size={14} aria-hidden />}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {rows.length === 0 ? (
                <div className="flex h-[365px] w-full items-center justify-center text-sm text-[var(--muted)]">
                    No invoices match your search or filters.
                </div>
            ) : (
                <div className="w-full h-[365px] overflow-hidden [&_.ag-row]:cursor-pointer">
                    <AgGridReact<HistoryEntry>
                        theme={settings.theme === "dark" ? darkTheme : lightTheme}
                        rowData={rows}
                        columnDefs={columnDefs}
                        getRowId={params => params.data.id}
                        rowHeight={64}
                        headerHeight={0}
                        suppressHorizontalScroll
                        suppressCellFocus
                        autoSizeStrategy={{ type: 'fitGridWidth' }}
                        onRowClicked={event => {
                            if (event.data) onOpen(event.data.id)
                        }}
                    />
                </div>
            )}
        </div>
    )
}
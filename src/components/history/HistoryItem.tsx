import { useState, useMemo, useRef, useEffect } from "react"
import { AgGridReact } from "ag-grid-react"
import { 
    ColDef, 
    ModuleRegistry, 
    AllCommunityModule, 
    ICellRendererParams, 
    ValueGetterParams 
} from "ag-grid-community"
import { ChevronRight, Search, Filter, Check, ArrowDownUp } from "lucide-react"
import type { HistoryEntry, RiskLevel, UserSettings } from "../../types.js"
import { LEVEL_META, formatDateTime, formatMoney } from "../../lib/risk.js"

// Rejestracja modułów AG Grid Community
ModuleRegistry.registerModules([AllCommunityModule]);

interface HistoryItemProps {
    data: HistoryEntry[]
    settings: UserSettings
    onOpen: (id: string) => void
}

export default function HistoryItem({ data, settings, onOpen }: HistoryItemProps) {
    const [searchQuery, setSearchQuery] = useState("")
    const [riskFilters, setRiskFilters] = useState({
        high: true,
        medium: true,
        low: true,
    })
    const [sortMode, setSortMode] = useState<"date-desc" | "price-desc" | "price-asc">("date-desc")
    const [isFilterOpen, setIsFilterOpen] = useState(false)

    const filterRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (filterRef.current && !filterRef.current.contains(event.target as Node)) {
                setIsFilterOpen(false)
            }
        }
        document.addEventListener("mousedown", handleClickOutside)
        return () => document.removeEventListener("mousedown", handleClickOutside)
    }, [])

    const stats = useMemo(() => {
        const totalChecked = data.length
        const highRiskCount = data.filter(item => item.level === 'high').length
        const flaggedSum = data
            .filter(item => item.level === 'high')
            .reduce((sum, item) => sum + item.invoice.amount, 0)

        const formattedFlagged = flaggedSum >= 1000 
            ? `$${(flaggedSum / 1000).toFixed(1)}k` 
            : formatMoney(flaggedSum, data[0]?.invoice.currency || 'USD')

        return {
            totalChecked,
            highRiskCount,
            flaggedAmount: formattedFlagged
        }
    }, [data])

    const processedData = useMemo(() => {
        return data
            .filter(item => {
                const matchesSearch = item.invoice.supplier.name.toLowerCase().includes(searchQuery.toLowerCase())
                if (!matchesSearch) return false

                if (item.level === 'high' && !riskFilters.high) return false
                if (item.level === 'medium' && !riskFilters.medium) return false
                if (item.level === 'low' && !riskFilters.low) return false
                return true
            })
            .sort((a, b) => {
                if (sortMode === "price-desc") return b.invoice.amount - a.invoice.amount
                if (sortMode === "price-asc") return a.invoice.amount - b.invoice.amount
                return new Date(b.checkedAt).getTime() - new Date(a.checkedAt).getTime()
            })
    }, [data, searchQuery, riskFilters, sortMode])

    const columnDefs = useMemo<ColDef<HistoryEntry>[]>(() => [
        {
            field: "level",
            headerName: "",
            width: 64,
            pinned: 'left',
            cellRenderer: (params: ICellRendererParams<HistoryEntry, RiskLevel>) => {
                const levelKey = params.value || 'low'
                const meta = LEVEL_META[levelKey]
                const Icon = meta.icon
                return (
                    <div className="flex items-center h-full px-2">
                        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${meta.soft} ${meta.text}`}>
                            <Icon size={18} aria-hidden />
                        </span>
                    </div>
                )
            }
        },
        {
            headerName: "Description",
            flex: 2,
            minWidth: 180,
            valueGetter: (params: ValueGetterParams<HistoryEntry>) => params.data?.invoice.supplier.name,
            cellRenderer: (params: ICellRendererParams<HistoryEntry>) => {
                const entry = params.data
                if (!entry) return null
                return (
                    <div className="flex flex-col justify-center h-full py-1 min-w-0">
                        <span className="block truncate text-sm font-semibold text-[var(--text)]">
                            {entry.invoice.supplier.name}
                        </span>
                        <span className="block text-xs text-[var(--muted)]">
                            {formatDateTime(entry.checkedAt)}
                        </span>
                    </div>
                )
            }
        },
        {
            headerName: "Amount",
            flex: 1.2,
            minWidth: 120,
            valueGetter: (params: ValueGetterParams<HistoryEntry>) => params.data?.invoice.amount,
            cellRenderer: (params: ICellRendererParams<HistoryEntry>) => {
                const entry = params.data
                if (!entry) return null
                const meta = LEVEL_META[entry.level]
                return (
                    <div className="flex flex-col justify-center items-end h-full py-1">
                        <span className="block text-sm font-semibold text-[var(--text)]">
                            {formatMoney(entry.invoice.amount, entry.invoice.currency)}
                        </span>
                        <span className={`block text-xs font-medium ${meta.text}`}>
                            {meta.label}
                        </span>
                    </div>
                )
            }
        },
        {
            headerName: "",
            width: 48,
            pinned: 'right',
            cellRenderer: () => (
                <div className="flex items-center justify-end h-full pr-2">
                    <ChevronRight size={16} className="text-[var(--muted)]" aria-hidden />
                </div>
            )
        }
    ], [])

    const gridThemeClass = settings.theme === 'dark' ? 'ag-theme-quartz-dark' : 'ag-theme-quartz';

    return (
        <div className="flex flex-col gap-4 p-4 w-full">
            {/* 1. Statystyki */}
            <div className="grid grid-cols-3 gap-2 py-2 border-b border-[var(--border)] text-center">
                <div>
                    <span className="block text-xs text-[var(--muted)]">Invoices checked</span>
                    <span className="text-xl font-bold text-[var(--text)]">{stats.totalChecked}</span>
                </div>
                <div>
                    <span className="block text-xs text-[var(--muted)]">High risk</span>
                    <span className="text-xl font-bold text-red-500">{stats.highRiskCount}</span>
                </div>
                <div>
                    <span className="block text-xs text-[var(--muted)]">Flagged amount</span>
                    <span className="text-xl font-bold text-[var(--text)]">{stats.flaggedAmount}</span>
                </div>
            </div>

            {/* 2. Nagłówek i wyszukiwanie + filtr */}
            <div className="flex flex-col gap-2">
                <h3 className="text-sm font-semibold text-[var(--text)]">Invoice audit log</h3>
                
                <div className="flex items-center gap-2 relative">
                    <div className="relative flex-1">
                        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]" aria-hidden />
                        <input
                            type="text"
                            placeholder="Search supplier..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="w-full pl-9 pr-3 py-2 text-sm bg-[var(--card)] text-[var(--text)] border border-[var(--border)] rounded-xl focus:outline-none focus:ring-2 focus:ring-[var(--primary)] transition-colors shadow-sm"
                        />
                    </div>

                    <div className="relative" ref={filterRef}>
                        <button
                            onClick={() => setIsFilterOpen(!isFilterOpen)}
                            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-xl border border-[var(--border)] bg-[var(--card)] text-[var(--text)] shadow-sm hover:bg-[var(--primary-soft)] transition-colors"
                        >
                            <Filter size={16} /> Filters
                        </button>

                        {isFilterOpen && (
                            <div className="absolute right-0 mt-2 w-56 bg-[var(--card)] border border-[var(--border)] rounded-xl shadow-xl p-3 z-30 flex flex-col gap-3">
                                <div className="flex flex-col gap-1.5">
                                    <span className="text-xs font-semibold text-[var(--muted)] px-1">Risk level</span>
                                    <label className="flex items-center gap-2 text-xs font-medium cursor-pointer px-1 py-1 hover:bg-[var(--primary-soft)] rounded">
                                        <input
                                            type="checkbox"
                                            checked={riskFilters.high}
                                            onChange={e => setRiskFilters({ ...riskFilters, high: e.target.checked })}
                                            className="rounded border-gray-300 text-red-600 focus:ring-red-500"
                                        />
                                        <span className="text-red-500 font-semibold">High risk</span>
                                    </label>
                                    <label className="flex items-center gap-2 text-xs font-medium cursor-pointer px-1 py-1 hover:bg-[var(--primary-soft)] rounded">
                                        <input
                                            type="checkbox"
                                            checked={riskFilters.medium}
                                            onChange={e => setRiskFilters({ ...riskFilters, medium: e.target.checked })}
                                            className="rounded border-gray-300 text-amber-600 focus:ring-amber-500"
                                        />
                                        <span className="text-amber-500 font-semibold">Medium risk</span>
                                    </label>
                                    <label className="flex items-center gap-2 text-xs font-medium cursor-pointer px-1 py-1 hover:bg-[var(--primary-soft)] rounded">
                                        <input
                                            type="checkbox"
                                            checked={riskFilters.low}
                                            onChange={e => setRiskFilters({ ...riskFilters, low: e.target.checked })}
                                            className="rounded border-gray-300 text-emerald-600 focus:ring-emerald-500"
                                        />
                                        <span className="text-emerald-500 font-semibold">Low risk</span>
                                    </label>
                                </div>

                                <hr className="border-[var(--border)]" />

                                <div className="flex flex-col gap-1">
                                    <span className="text-xs font-semibold text-[var(--muted)] px-1 flex items-center gap-1">
                                        <ArrowDownUp size={12} /> Sort by
                                    </span>
                                    <button
                                        onClick={() => setSortMode("date-desc")}
                                        className={`flex items-center justify-between w-full text-left text-xs px-2 py-1.5 rounded hover:bg-[var(--primary-soft)] ${sortMode === 'date-desc' ? 'font-bold text-[var(--primary)]' : 'text-[var(--text)]'}`}
                                    >
                                        Date (newest) {sortMode === 'date-desc' && <Check size={14} />}
                                    </button>
                                    <button
                                        onClick={() => setSortMode("price-desc")}
                                        className={`flex items-center justify-between w-full text-left text-xs px-2 py-1.5 rounded hover:bg-[var(--primary-soft)] ${sortMode === 'price-desc' ? 'font-bold text-[var(--primary)]' : 'text-[var(--text)]'}`}
                                    >
                                        Price: highest first {sortMode === 'price-desc' && <Check size={14} />}
                                    </button>
                                    <button
                                        onClick={() => setSortMode("price-asc")}
                                        className={`flex items-center justify-between w-full text-left text-xs px-2 py-1.5 rounded hover:bg-[var(--primary-soft)] ${sortMode === 'price-asc' ? 'font-bold text-[var(--primary)]' : 'text-[var(--text)]'}`}
                                    >
                                        Price: lowest first {sortMode === 'price-asc' && <Check size={14} />}
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* 3. Tabela AG Grid */}
            <div className={`${gridThemeClass} w-full h-[380px] rounded-xl overflow-hidden border border-[var(--border)] shadow-sm`}>
                <AgGridReact<HistoryEntry>
                    rowData={processedData}
                    columnDefs={columnDefs}
                    rowHeight={64}
                    headerHeight={0}
                    autoSizeStrategy={{ type: 'fitGridWidth' }}
                    onRowClicked={event => {
                        if (event.data) {
                            onOpen(event.data.id)
                        }
                    }}
                    rowStyle={{ cursor: 'pointer' }}
                    suppressCellFocus={true}
                />
            </div>
        </div>
    )
}
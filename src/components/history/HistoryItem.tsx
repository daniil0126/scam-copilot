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
import { ArrowDownUp, Check, CheckCircle2, Filter, Search } from "lucide-react"
import type { HistoryEntry, RiskLevel, UserSettings } from "../../api/types.js"
import { LEVEL_META, formatDateTime, formatMoney } from "../../lib/risk.js"
import { usePayments } from "../../payments/context.js"

// Only the row model module is registered: a lighter bundle.
ModuleRegistry.registerModules([ClientSideRowModelModule])

type SortMode = "date-desc" | "price-desc" | "price-asc"
type PayFilter = "all" | "paid" | "unpaid"

const PAY_FILTERS: { value: PayFilter; label: string }[] = [
    { value: "all", label: "All" },
    { value: "paid", label: "Paid" },
    { value: "unpaid", label: "Not paid" },
]

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
    // A quiet hover: the same tint everywhere in the row, with no separate colour for any part of it.
    rowHoverColor: "color-mix(in srgb, var(--border) 45%, transparent)",
} as const

const lightTheme = themeQuartz.withPart(colorSchemeLight).withParams(gridParams)
const darkTheme = themeQuartz.withPart(colorSchemeDark).withParams(gridParams)

// Amounts in the statistics are formatted the English way, for example $2.5k.
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

// One row of the list. A row is two lines: who and how much, then how it was judged and what can be done (tick it, Pay it, or
// get it checked). Opening the check is a click anywhere else on the row; the tick, Pay and Check now are marked `data-no-open`.
const columnDefs: ColDef<HistoryEntry>[] = [{ flex: 1 }]  // required by the grid; the rows are drawn full width
const canCheckNow = (entry: HistoryEntry, pay: ReturnType<typeof usePayments>) => {
    const { view, started } = payState(entry, pay)
    const code = view?.reasons[0]?.code
    return !started && !!entry.invoiceId && (code === "not_checked" || code === "changed")
}
const ROW_HEIGHT = 84
const SHORT_ROW_HEIGHT = 68

function payState(entry: HistoryEntry, pay: ReturnType<typeof usePayments>) {
    const view = entry.invoiceId ? pay.views[entry.invoiceId] : undefined
    const started = !!entry.invoiceId && (pay.inProgress.has(entry.invoiceId) || pay.paid.has(entry.invoiceId))
    return { view, started, payable: !!view?.eligible && !started }
}

function PayRow({ data }: ICellRendererParams<HistoryEntry>) {
    const pay = usePayments()
    if (!data) return null
    const meta = LEVEL_META[data.level]
    const Icon = meta.icon
    const { view, started, payable } = payState(data, pay)
    const id = data.invoiceId
    const name = data.invoice.supplier.name.trim() || (data.invoice.number ? `Invoice #${data.invoice.number}` : "Unknown supplier")
    const title = `${name}${data.invoice.number ? ` #${data.invoice.number}` : ""}`
    const amount = formatMoney(data.invoice.amount, data.invoice.currency)
    const ticked = !!id && pay.selection.has(id)
    const code = view?.reasons[0]?.code
    const canCheck = !!id && !started && (code === "not_checked" || code === "changed")
    const why = started ? "Payment already started" : view ? (view.reasons[0]?.text ?? "Cannot be paid from here") : id ? "Checking whether it can be paid" : "No PayPal invoice to pay"
    const loud = data.level === "high" || data.level === "medium"
    // An invoice PayPal no longer lets anyone pay (paid, cancelled, ...) is said so instead of repeating its old risk label.
    const closed = !started && (code === "paid" || code === "not_payable")
    const closedText = code === "paid" ? "Paid" : view?.status ? view.status.charAt(0) + view.status.slice(1).toLowerCase().replaceAll("_", " ") : "Not open for payment"
    return (
        <div
            style={{ borderLeftColor: loud ? meta.stroke : "transparent" }}
            className={`flex h-full cursor-pointer items-stretch border-l-[3px] ${ticked ? "bg-[var(--primary-soft)]" : ""}`}
        >
            <label data-no-open className="grid w-11 shrink-0 cursor-pointer place-items-center self-start pt-1.5 has-[:disabled]:cursor-not-allowed" style={{ height: 44 }}>
                <input
                    type="checkbox"
                    className="h-5 w-5 cursor-pointer accent-[var(--primary)] disabled:cursor-not-allowed disabled:opacity-45"
                    checked={ticked}
                    disabled={!payable}
                    onChange={e => { if (id) pay.toggle(id, e.target.checked) }}
                    aria-describedby={payable ? undefined : `why-${data.id}`}
                />
                <span className="sr-only">Select {title}, {amount}</span>
                {!payable && <span id={`why-${data.id}`} className="sr-only">{why}</span>}
            </label>
            <div className="flex min-w-0 flex-1 flex-col justify-center gap-1 py-2 pr-3">
                <div className="flex items-baseline justify-between gap-3">
                    <span className="line-clamp-1 break-words text-sm font-semibold leading-5 [overflow-wrap:anywhere]">{name}</span>
                    <span className="whitespace-nowrap text-sm font-semibold tabular-nums leading-5">{amount}</span>
                </div>
                <div className="flex min-h-[1.25rem] items-center justify-between gap-2">
                    <span className="min-w-0 truncate text-[13px] leading-5 text-[var(--muted)]">
                        {formatDateTime(data.checkedAt)}
                        {" · "}
                        {started
                            ? (pay.paid.has(id ?? "")
                                ? <span className="font-medium text-[var(--success)]"><CheckCircle2 size={13} className="mb-0.5 mr-0.5 inline" aria-hidden />Paid</span>
                                : <span className="text-[var(--primary)]">Payment started</span>)
                            : closed
                            ? <span className={code === "paid" ? "font-medium text-[var(--success)]" : ""}>{code === "paid" && <CheckCircle2 size={13} className="mb-0.5 mr-0.5 inline" aria-hidden />}{closedText}</span>
                            : <span className={`font-medium ${payable ? "text-[var(--success)]" : meta.text}`}><Icon size={13} className="mb-0.5 mr-0.5 inline" aria-hidden />{payable ? "No warning signs" : meta.label}</span>}
                    </span>
                    {payable && id && (
                        <button
                            data-no-open
                            onClick={e => pay.review([id], "ui", e.currentTarget)}
                            aria-label={`Pay ${title}`}
                            className="h-8 shrink-0 rounded-md border border-[var(--primary)]/60 px-3 text-[13px] font-medium text-[var(--primary)] hover:bg-[var(--primary-soft)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"
                        >
                            Pay
                        </button>
                    )}
                    {canCheck && id && (
                        <button
                            data-no-open
                            onClick={() => { void pay.checkNow(id) }}
                            disabled={pay.checking.has(id)}
                            aria-label={`Check ${title} now`}
                            className="min-h-11 shrink-0 px-1.5 text-[13px] font-medium text-[var(--primary)] underline underline-offset-2 disabled:no-underline disabled:opacity-70 focus-visible:outline-2 focus-visible:outline-[var(--primary)]"
                        >
                            {pay.checking.has(id) ? "Checking…" : "Check now"}
                        </button>
                    )}
                </div>
            </div>
        </div>
    )
}

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
    const [payFilter, setPayFilter] = useState<PayFilter>("all")
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
    const pay = usePayments()
    const { ensure } = pay
    const gridRef = useRef<AgGridReact<HistoryEntry>>(null)

    const rows = useMemo(() => {
        const query = searchQuery.trim().toLowerCase()
        // Paid is what PayPal says (the gate's verdict) or what a payment just made in this panel confirmed.
        const isPaid = (entry: HistoryEntry) =>
            !!entry.invoiceId && (pay.paid.has(entry.invoiceId) || !!pay.views[entry.invoiceId]?.reasons.some(r => r.code === "paid"))
        return data
            .filter(
                entry =>
                    riskFilters[entry.level] &&
                    (payFilter === "all" || isPaid(entry) === (payFilter === "paid")) &&
                    entry.invoice.supplier.name.toLowerCase().includes(query)
            )
            .sort(COMPARATORS[sortMode])
    }, [data, searchQuery, riskFilters, sortMode, payFilter, pay.paid, pay.views])

    // Who may be paid is the server's verdict, asked for the invoices in the list.
    const invoiceIds = rows.map(r => r.invoiceId).filter((id): id is string => !!id).join(",")
    useEffect(() => { ensure(invoiceIds ? invoiceIds.split(",") : []) }, [invoiceIds, ensure])
    const payableIds = rows.filter(r => payState(r, pay).payable).map(r => r.invoiceId as string)
    const tickedCount = payableIds.filter(id => pay.selection.has(id)).length
    // Rows that offer Pay or Check now are taller than the rest; a verdict arriving changes which those are.
    useEffect(() => { gridRef.current?.api?.resetRowHeights() }, [pay.views, pay.inProgress, pay.paid])

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
                            {payFilter !== "all" && <span className="h-2 w-2 rounded-full bg-[var(--primary)]" aria-label="A payment filter is on" />}
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

                                <div role="radiogroup" aria-label="Payment" className="flex flex-col gap-1">
                                    <span className="text-xs font-semibold text-[var(--muted)] px-1">Payment</span>
                                    {PAY_FILTERS.map(option => (
                                        <label key={option.value} className={`flex cursor-pointer items-center gap-2 rounded px-1 py-1.5 text-xs hover:bg-[var(--primary-soft)] ${payFilter === option.value ? "font-bold text-[var(--primary)]" : "text-[var(--text)]"}`}>
                                            <input type="radio" name="pay-filter" checked={payFilter === option.value} onChange={() => setPayFilter(option.value)} className="accent-[var(--primary)]" />
                                            {option.label}
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

            {payableIds.length > 0 && (
                <label className="-mt-2 flex min-h-11 cursor-pointer items-center text-[13px] text-[var(--muted)]">
                    <span className="grid h-11 w-8 place-items-center">
                        <input
                            type="checkbox"
                            className="h-5 w-5 cursor-pointer accent-[var(--primary)]"
                            checked={tickedCount === payableIds.length}
                            ref={el => { if (el) el.indeterminate = tickedCount > 0 && tickedCount < payableIds.length }}
                            onChange={e => pay.setMany(payableIds, e.target.checked)}
                        />
                    </span>
                    Select all with no warning signs ({payableIds.length})
                </label>
            )}

            {rows.length === 0 ? (
                <div className="flex h-[365px] w-full items-center justify-center text-sm text-[var(--muted)]">
                    No invoices match your search or filters.
                </div>
            ) : (
                <div className="h-[440px] w-full overflow-hidden [&_.ag-row]:cursor-pointer">
                    <AgGridReact<HistoryEntry>
                        ref={gridRef}
                        theme={settings.theme === "dark" ? darkTheme : lightTheme}
                        rowData={rows}
                        columnDefs={columnDefs}
                        isFullWidthRow={() => true}
                        fullWidthCellRenderer={PayRow}
                        getRowId={params => params.data.id}
                        getRowHeight={params => (params.data && (payState(params.data, pay).payable || canCheckNow(params.data, pay)) ? ROW_HEIGHT : SHORT_ROW_HEIGHT)}
                        headerHeight={0}
                        suppressHorizontalScroll
                        suppressCellFocus
                        onRowClicked={event => {
                            const target = event.event?.target
                            if (target instanceof Element && target.closest("[data-no-open]")) return  // the tick, Pay and Check now are not "open"
                            if (event.data) onOpen(event.data.id)
                        }}
                    />
                </div>
            )}
        </div>
    )
}
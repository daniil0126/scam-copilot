import { useEffect, useState } from "react"
import type { GridApi } from "ag-grid-community"
import { Download, Search } from "lucide-react"
import { csvFileName, csvSafe } from "./csv.js"

type Props = {
    api: GridApi | null
    // Rows the grid was given: the "N of M" counter shows how many of them the filters leave.
    total: number
    // Used in the CSV file name: scam-copilot-<exportName>-YYYY-MM-DD.csv
    exportName: string
    label: string
}

// The search box, the "N of M" counter and the CSV button shared by the tables.
export default function GridToolbar({ api, total, exportName, label }: Props) {
    const [query, setQuery] = useState("")
    const [shown, setShown] = useState(total)

    useEffect(() => {
        if (!api) return
        const count = () => setShown(api.getDisplayedRowCount())
        api.addEventListener("modelUpdated", count)
        return () => { if (!api.isDestroyed()) api.removeEventListener("modelUpdated", count) }
    }, [api])

    const exportCsv = () => api?.exportDataAsCsv({
        fileName: csvFileName(exportName),
        processCellCallback: p => csvSafe(p.formatValue ? p.formatValue(p.value) : p.value),
    })

    return (
        <div className="mt-2 flex items-center gap-2">
            <label className="relative min-w-0 flex-1">
                <span className="sr-only">{label}</span>
                <Search size={14} aria-hidden className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--muted)]" />
                <input
                    value={query}
                    onChange={e => { setQuery(e.target.value); api?.setGridOption("quickFilterText", e.target.value) }}
                    placeholder={label}
                    className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] py-1.5 pl-8 pr-2 text-xs text-[var(--text)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
                />
            </label>
            <span className="shrink-0 text-xs tabular-nums text-[var(--muted)]" aria-live="polite">{shown} of {total}</span>
            <button
                onClick={exportCsv}
                className="inline-flex min-h-8 shrink-0 cursor-pointer items-center gap-1 rounded-lg border border-[var(--border)] px-2.5 text-xs font-semibold text-[var(--text)] hover:bg-[var(--primary-soft)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"
            >
                <Download size={13} aria-hidden /> CSV
            </button>
        </div>
    )
}

import { useEffect, useState } from "react"
import { ArrowLeft, History, Loader2 } from "lucide-react"
import { fetchHistory } from "../../api/client.js"
import HistoryItem from "./HistoryItem.js"
import VerificationView from "../check/VerificationView.js"
import type { HistoryEntry, UserSettings } from "../../api/types.js"

type HistoryViewProps = {
    settings: UserSettings
}

export default function HistoryView({ settings }: HistoryViewProps) {
    const [openId, setOpenId] = useState<string | null>(null)
    const [history, setHistory] = useState<HistoryEntry[] | null>(null)
    const [error, setError] = useState<string | null>(null)
    const opened = history?.find(h => h.id === openId)

    useEffect(() => {
        let cancelled = false
        fetchHistory()
            .then(data => { if (!cancelled) setHistory(data) })
            .catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : "Could not load the history.") })
        return () => { cancelled = true }
    }, [])

    if (error) {
        return <p role="alert" className="p-6 text-center text-sm font-medium text-[var(--danger)]">{error}</p>
    }

    if (!history) {
        return (
            <div role="status" className="flex items-center justify-center gap-2 p-10 text-sm text-[var(--muted)]">
                <Loader2 size={18} className="motion-safe:animate-spin" aria-hidden /> Loading history...
            </div>
        )
    }

    if (opened) {
        return (
            <div>
                <button
                    onClick={() => setOpenId(null)}
                    className="flex items-center gap-1.5 px-4 pt-3 text-sm font-medium text-[var(--primary)] focus-visible:outline-2 focus-visible:outline-[var(--primary)]"
                >
                    <ArrowLeft size={16} aria-hidden /> Back to history
                </button>
                <VerificationView key={opened.id} result={opened} />
            </div>
        )
    }

    if (history.length === 0) {
        return (
            <div className="flex flex-col items-center gap-2 p-10 text-center text-[var(--muted)]">
                <History size={32} aria-hidden />
                <p className="text-sm">No checks yet. Analysed invoices will appear here.</p>
            </div>
        )
    }

    return (
        <HistoryItem data={history} settings={settings} onOpen={(id) => setOpenId(id)} />
    )
}
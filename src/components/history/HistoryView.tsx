import { useEffect, useState } from "react"
import { ArrowLeft, History, Loader2 } from "lucide-react"
import { fetchHistory } from "../../api/client.js"
import HistoryItem from "./HistoryItem.js"
import VerificationView from "../check/VerificationView.js"
import type { HistoryEntry, UserSettings } from "../../api/types.js"

type HistoryViewProps = {
    settings: UserSettings
    // Changes when the background monitor stores something new, so the list reloads without a click.
    reloadKey?: string
    // The open check lives in the parent so another tab can open a given one.
    openId: string | null
    onOpenChange: (id: string | null) => void
    // Set when the check was opened from another tab: the button then says where it goes and takes the user back there.
    backLabel?: string
    onBack?: () => void
}

export default function HistoryView({ settings, reloadKey, openId, onOpenChange, backLabel, onBack }: HistoryViewProps) {
    const [history, setHistory] = useState<HistoryEntry[] | null>(null)
    const [error, setError] = useState<string | null>(null)
    const opened = history?.find(h => h.id === openId)

    useEffect(() => {
        let cancelled = false
        fetchHistory()
            .then(data => { if (!cancelled) setHistory(data) })
            .catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : "Could not load the history.") })
        return () => { cancelled = true }
    }, [reloadKey])

    const goBack = () => (onBack ? onBack() : onOpenChange(null))

    // The usual ways of going back besides the button: Alt+Left, Cmd+[ and the back button of a mouse.
    const hasOpened = Boolean(opened)
    useEffect(() => {
        if (!hasOpened) return
        const onKey = (e: KeyboardEvent) => {
            if ((e.altKey && e.key === "ArrowLeft") || (e.metaKey && e.key === "[")) {
                e.preventDefault()
                goBack()
            }
        }
        const onMouse = (e: MouseEvent) => {
            if (e.button === 3) {
                e.preventDefault()
                goBack()
            }
        }
        window.addEventListener("keydown", onKey)
        window.addEventListener("mouseup", onMouse)
        return () => {
            window.removeEventListener("keydown", onKey)
            window.removeEventListener("mouseup", onMouse)
        }
    })

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
                    onClick={goBack}
                    className="flex items-center gap-1.5 px-4 pt-3 text-sm font-medium text-[var(--primary)] focus-visible:outline-2 focus-visible:outline-[var(--primary)]"
                >
                    <ArrowLeft size={16} aria-hidden /> Back to {backLabel ?? "history"}
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
        <HistoryItem data={history} settings={settings} onOpen={onOpenChange} />
    )
}
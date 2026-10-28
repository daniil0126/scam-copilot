import { useState } from "react"
import { ArrowLeft, History } from "lucide-react"
import { HISTORY } from "../../data/mock.js"
import HistoryItem from "./HistoryItem.js"
import VerificationView from "../check/VerificationView.js"
import type { UserSettings } from "../../types.js"

type HistoryViewProps = {
    settings: UserSettings
}

export default function HistoryView({ settings }: HistoryViewProps) {
    const [openId, setOpenId] = useState<string | null>(null)
    const opened = HISTORY.find(h => h.id === openId)

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

    if (HISTORY.length === 0) {
        return (
            <div className="flex flex-col items-center gap-2 p-10 text-center text-[var(--muted)]">
                <History size={32} aria-hidden />
                <p className="text-sm">No checks yet. Analysed invoices will appear here.</p>
            </div>
        )
    }

    return (
        <HistoryItem data={HISTORY} settings={settings} onOpen={(id) => setOpenId(id)} />
    )
}
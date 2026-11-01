import { useEffect, useState } from "react"
import { MessageCircle } from "lucide-react"
import { fetchAiStatus, sendChatStream } from "../../api/client.js"
import type { InvoiceRef, Message, TraceStep } from "../../api/types.js"
import { applyEvent } from "../../lib/chatTrace.js"
import LiveTrace from "./LiveTrace.js"
import ChatBox from "../ChatBox.js"
import MessageList from "../MessageList.js"

// `checkId`: the check currently shown on the Check tab, so questions can be about that invoice.
export default function ChatTab({ checkId, onOpenInvoice, active }: { checkId: string | null, onOpenInvoice: (invoice: InvoiceRef) => Promise<void>, active: boolean }) {
    const [messages, setMessages] = useState<Message[]>([])
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState<string | null>(null)
    // The server lists tools in /ai/status only when the assistant can really read PayPal.
    const [canReadPayPal, setCanReadPayPal] = useState(false)
    const [opening, setOpening] = useState<string | null>(null)  // the invoice whose check is being opened
    const [live, setLive] = useState<TraceStep[]>([])  // the steps of the question being answered now

    useEffect(() => {
        fetchAiStatus().then(s => setCanReadPayPal((s.tools?.length ?? 0) > 0)).catch(() => setCanReadPayPal(false))
    }, [])

    const openInvoice = async (invoice: InvoiceRef) => {
        setOpening(invoice.id)
        setError(null)
        try {
            await onOpenInvoice(invoice)
        } catch (e) {
            setError(e instanceof Error ? e.message : "Could not open this invoice.")
        } finally {
            setOpening(null)
        }
    }

    const send = async (text: string) => {
        const next: Message[] = [...messages, { id: Date.now(), role: "user", message: text }]
        setMessages(next)
        setBusy(true)
        setError(null)
        setLive([])
        try {
            const turns = next.map(m => ({ role: m.role === "user" ? "user" as const : "assistant" as const, content: m.message }))
            let steps: TraceStep[] = []
            let answered = false
            await sendChatStream(turns, checkId, event => {
                if (event.type === "error") throw new Error(event.message)
                if (event.type === "answer") {
                    answered = true
                    setMessages(prev => [...prev, { id: Date.now(), role: "system", message: event.reply, tools: event.toolsUsed, trace: steps.some(s => s.kind !== "model") ? steps : undefined, invoices: event.invoices, table: event.table ?? undefined }])
                    return
                }
                steps = applyEvent(steps, event)
                setLive(steps)
            })
            if (!answered) throw new Error("The server stopped before it answered. Try again.")
        } catch (e) {
            setError(e instanceof Error ? e.message : "Something went wrong.")
        } finally {
            setBusy(false)
            setLive([])
        }
    }

    return (
        <div className="flex h-full flex-col px-4 pb-4 pt-2">
            {messages.length === 0 && !busy ? (
                <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center text-[var(--muted)]">
                    <MessageCircle size={32} aria-hidden />
                    <p className="text-sm">Ask a question about an invoice or a payment.</p>
                </div>
            ) : (
                <MessageList
                    messages={messages}
                    pendingKey={live.length}
                    active={active}
                    opening={opening}
                    onOpenInvoice={invoice => { void openInvoice(invoice) }}
                    pending={busy ? <LiveTrace steps={live} canReadPayPal={canReadPayPal} /> : null}
                />
            )}
            {error && <p role="alert" className="py-1 text-xs font-medium text-[var(--danger)]">{error}</p>}
            <div className="pt-2"><ChatBox onSend={send} /></div>
        </div>
    )
}

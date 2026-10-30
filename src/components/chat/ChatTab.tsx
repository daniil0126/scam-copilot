import { useState } from "react"
import { Loader2, MessageCircle } from "lucide-react"
import { sendChat } from "../../api/client.js"
import type { Message } from "../../api/types.js"
import ChatBox from "../ChatBox.js"
import MessageList from "../MessageList.js"

// `checkId`: the check currently shown on the Check tab, so questions can be about that invoice.
export default function ChatTab({ checkId }: { checkId: string | null }) {
    const [messages, setMessages] = useState<Message[]>([])
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const send = async (text: string) => {
        const next: Message[] = [...messages, { id: Date.now(), role: "user", message: text }]
        setMessages(next)
        setBusy(true)
        setError(null)
        try {
            const turns = next.map(m => ({ role: m.role === "user" ? "user" as const : "assistant" as const, content: m.message }))
            const { reply } = await sendChat(turns, checkId)
            setMessages(prev => [...prev, { id: Date.now(), role: "system", message: reply }])
        } catch (e) {
            setError(e instanceof Error ? e.message : "Something went wrong.")
        } finally {
            setBusy(false)
        }
    }

    return (
        <div className="flex h-full flex-col px-4 pb-4 pt-2">
            {messages.length === 0 ? (
                <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center text-[var(--muted)]">
                    <MessageCircle size={32} aria-hidden />
                    <p className="text-sm">Ask a question about an invoice or a payment.</p>
                </div>
            ) : (
                <MessageList messages={messages} />
            )}
            {busy && (
                <p role="status" className="flex items-center gap-2 py-1 text-xs text-[var(--muted)]">
                    <Loader2 size={14} className="motion-safe:animate-spin" aria-hidden /> Thinking...
                </p>
            )}
            {error && <p role="alert" className="py-1 text-xs font-medium text-[var(--danger)]">{error}</p>}
            <div className="pt-2"><ChatBox onSend={send} /></div>
        </div>
    )
}

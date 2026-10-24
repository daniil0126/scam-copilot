import { useState } from "react"
import { MessageCircle } from "lucide-react"
import type { Message } from "../../types.js"
import ChatBox from "../ChatBox.js"
import MessageList from "../MessageList.js"

export default function ChatTab() {
    const [messages, setMessages] = useState<Message[]>([])

    const send = (text: string) =>
        setMessages(prev => [...prev, { id: Date.now(), role: "user", message: text }])

    return (
        <div className="flex h-full flex-col px-4 pb-4 pt-2">
            {messages.length === 0 ? (
                <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center text-[var(--muted)]">
                    <MessageCircle size={32} aria-hidden />
                    <p className="text-sm">Ask a question about an invoice or a payment.</p>
                    <p className="text-xs">Demo: replies are not connected yet.</p>
                </div>
            ) : (
                <MessageList messages={messages} />
            )}
            <div className="pt-2"><ChatBox onSend={send} /></div>
        </div>
    )
}

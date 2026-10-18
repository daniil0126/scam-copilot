import { useEffect, useState } from "react"
import { MessageCircle, X } from "lucide-react"
import { Message } from "../types.js"
import ChatBox from "./ChatBox.js"
import MessageList from "./MessageList.js"

export default function ChatWidget() {
    const [open, setOpen] = useState(false)
    const [messages, setMessages] = useState<Message[]>([])

    useEffect(() => {
        if (!open) return
        const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false)
        window.addEventListener("keydown", onKey)
        return () => window.removeEventListener("keydown", onKey)
    }, [open])

    const send = (text: string) =>
        setMessages(prev => [...prev, { id: Date.now(), role: "user", message: text }])

    return (
        <div className="fixed bottom-4 right-4 z-50 flex flex-col items-end gap-3">
            {open && (
                <section
                    aria-label="Mini chat"
                    className="flex h-[min(420px,70vh)] w-[min(340px,calc(100vw-2rem))] flex-col overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--bg)] shadow-xl"
                >
                    <header className="flex items-center justify-between bg-[var(--navy)] px-3 py-2 text-white">
                        <h2 className="text-sm font-semibold">Chat</h2>
                        <button
                            aria-label="Close chat"
                            onClick={() => setOpen(false)}
                            className="rounded p-1 hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-white"
                        >
                            <X size={16} />
                        </button>
                    </header>
                    <div className="flex min-h-0 flex-1 flex-col px-3 pb-3 pt-1">
                        <MessageList messages={messages} />
                        <div className="pt-2"><ChatBox onSend={send} /></div>
                    </div>
                </section>
            )}
            <button
                aria-label={open ? "Close chat" : "Open chat"}
                aria-expanded={open}
                onClick={() => setOpen(o => !o)}
                className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--primary)] text-white shadow-lg transition-transform hover:scale-105 active:scale-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"
            >
                {open ? <X size={22} /> : <MessageCircle size={22} />}
            </button>
        </div>
    )
}

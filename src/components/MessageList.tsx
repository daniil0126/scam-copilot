import { useEffect, useRef, type ReactNode } from "react"
import MessageBox from "./MessageBox.js"
import type { InvoiceRef, Message } from "../api/types.js"

// `pending` is drawn after the last message: the answer that is being worked on.
export default function MessageList({messages, pending, pendingKey, opening, onOpenInvoice, active = true}: {messages: Message[], pending?: ReactNode, pendingKey?: number, opening?: string | null, onOpenInvoice?: (invoice: InvoiceRef) => void, active?: boolean}){
    const listRef = useRef<HTMLDivElement>(null)
    // A hidden tab loses its scroll position; it is saved while the chat is shown and put back when it is shown again.
    const saved = useRef(0)
    useEffect(() => {
        const list = listRef.current
        if (active && list) list.scrollTop = saved.current
    }, [active])

    // Keep the newest message in view.
    useEffect(() => {
        const list = listRef.current
        if (list) list.scrollTop = list.scrollHeight
    }, [messages.length, pendingKey])

    return (
        <div ref={listRef} onScroll={e => { if (active) saved.current = e.currentTarget.scrollTop }} role="log" aria-label="Conversation" className="flex-1 flex flex-col w-full overflow-y-auto">
            {messages.map(m => <MessageBox key={m.id} id={m.id} message={m.message} role={m.role} tools={m.tools} trace={m.trace} invoices={m.invoices} table={m.table} links={onOpenInvoice ? { opening: opening ?? null, onOpen: onOpenInvoice } : undefined} />)}
            {pending}
        </div>
    )
}

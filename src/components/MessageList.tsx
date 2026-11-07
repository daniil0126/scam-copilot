import { useEffect, useRef, type ReactNode } from "react"
import MessageBox from "./MessageBox.js"
import type { InvoiceRef, Message } from "../api/types.js"

// `pending` is drawn after the last message: the answer that is being worked on.
export default function MessageList({messages, pending, pendingKey, opening, onOpenInvoice, onPay, active = true}: {messages: Message[], pending?: ReactNode, pendingKey?: number, opening?: string | null, onOpenInvoice?: (invoice: InvoiceRef) => void, onPay?: (ids?: string[]) => void, active?: boolean}){
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
        <div ref={listRef} onScroll={e => { if (active) saved.current = e.currentTarget.scrollTop }} role="log" aria-label="Conversation" className="flex-1 flex flex-col gap-2 w-full overflow-y-auto">
            {messages.map((m, i) => <MessageBox key={m.id} spaced={i > 0 && messages[i - 1].role !== m.role} id={m.id} message={m.message} role={m.role} tools={m.tools} trace={m.trace} invoices={m.invoices} table={m.table} proposal={m.proposal} onPay={onPay} links={onOpenInvoice ? { opening: opening ?? null, onOpen: onOpenInvoice } : undefined} />)}
            {pending}
        </div>
    )
}

import { useEffect, useRef } from "react"
import MessageBox from "./MessageBox.js"
import type { Message } from "../api/types.js"

export default function MessageList({messages}: {messages: Message[]}){
    const listRef = useRef<HTMLDivElement>(null)

    // Keep the newest message in view.
    useEffect(() => {
        const list = listRef.current
        if (list) list.scrollTop = list.scrollHeight
    }, [messages.length])

    return (
        <div ref={listRef} role="log" aria-label="Conversation" className="flex-1 flex flex-col w-full overflow-y-auto">
            {messages.map(m => <MessageBox key={m.id} id={m.id} message={m.message} role={m.role} />)}
        </div>
    )
}

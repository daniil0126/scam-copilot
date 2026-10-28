import React from "react";
import { Message } from "../api/types.js";

export default function MessageBox(message: Message) {
    const isUser = message.role === "user"
    return (
        <div className={`max-w-[85%] px-3 py-2 mt-2 rounded-2xl text-sm ${isUser ? "self-end bg-[var(--primary)] text-white" : "self-start bg-[var(--card)] border border-[var(--border)] text-[var(--text)]"}`}>
            {message.message}
        </div>
    )
}
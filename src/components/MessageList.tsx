import React from "react";
import MessageBox from "./MessageBox.js";
import { Message } from "../types.js";

export default function MessageList({messages}: {messages: Message[]}){
    return (
        <div className="flex-1 flex flex-col w-full overflow-y-auto">
            {messages.map(m => <MessageBox key={m.id} id={m.id} message={m.message} role={m.role} />)}
        </div>
    )
}
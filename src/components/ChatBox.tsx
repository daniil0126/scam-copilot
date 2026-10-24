import { useState, useEffect, useRef, type ChangeEvent, type KeyboardEvent } from "react";

export default function ChatBox({onSend}: {onSend: (text: string) => void}) {
    const [message, setMessage] = useState<string>("");
    const textAreaRef = useRef<HTMLTextAreaElement>(null);

    useEffect(() => {
        const textArea = textAreaRef.current;
        if (textArea) {
            textArea.style.height = "auto";
            // A hidden tab reports a scrollHeight of 0; keep the natural height in that case.
            if (textArea.scrollHeight) textArea.style.height = `${textArea.scrollHeight}px`;
        }
    }, [message]);

    const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey){
            e.preventDefault()
            handleSend()
        }
    }

    const handleInputChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
        setMessage(e.target.value)
    }

    const handleSend = () => {
        if(!message.trim()) return
        onSend(message)
        setMessage('')
    }

    return (
        <>
        <div className="flex items-end border border-[var(--border)] bg-[var(--card)] shadow-sm w-full px-3 py-2 rounded-2xl focus-within:border-[var(--primary)]">
            <textarea
                ref={textAreaRef}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                value={message}
                className="flex-1 bg-transparent border-none text-[var(--text)] placeholder:text-[var(--muted)] resize-none h-auto max-h-[200px] p-2 outline-none text-sm leading-normal"
                placeholder="Describe your question"
                rows={1}
            ></textarea>
            <button
                id="sendBtn"
                aria-label="Send"
                onClick={handleSend}
                disabled={!message.trim()}
                className={`flex items-center w-8 h-8 border-none rounded-full bg-[var(--primary)] text-white justify-center cursor-pointer mb-0.5 transition-opacity disabled:opacity-40 disabled:cursor-default focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]`}
                >
                
                <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" >
                    <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path>
                </svg>
            </button>
        </div>
        </>
    );
}

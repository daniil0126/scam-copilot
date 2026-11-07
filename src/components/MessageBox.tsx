import React, { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Message } from "../api/types.js";
import Markdown, { type InvoiceLinks } from "./chat/Markdown.js";
import TraceView from "./chat/TraceView.js";
import InvoiceTable from "./chat/InvoiceTable.js";
import PaymentProposalCard from "../payments/PaymentProposalCard.js";

// `spaced`: the speaker changed since the previous message, so it gets more room above it than a message of the same speaker.
export default function MessageBox(message: Message & { links?: Omit<InvoiceLinks, "invoices"> , spaced?: boolean, onPay?: (ids?: string[]) => void }) {
    const isUser = message.role === "user"
    const [stepsOpen, setStepsOpen] = useState(false)
    const steps = message.trace ?? []
    const tools = message.tools ?? []
    const failed = steps.some(s => s.state === "failed")
    // "Used list_invoices · 3 steps": what happened, before the answer, like the folded steps of other chat assistants.
    const summary = `${tools.length > 0 ? `Used ${tools.join(", ")}` : "Steps"} · ${steps.length} ${steps.length === 1 ? "step" : "steps"}${failed ? " · one failed" : ""}`
    return (
        <div className={`shrink-0 ${message.table || message.proposal ? "w-full max-w-full overflow-clip" : "max-w-[96%]"} px-3.5 py-2.5 ${message.spaced ? "mt-3" : ""} rounded-2xl text-sm leading-relaxed ${isUser ? "self-end bg-[var(--primary)] text-white" : "self-start bg-[var(--card)] border border-[var(--border)] text-[var(--text)]"}`}>
            {steps.length > 0 && (
                <div className="mb-2 border-b border-[var(--border)] pb-2">
                    <button
                        onClick={() => setStepsOpen(o => !o)}
                        aria-expanded={stepsOpen}
                        className="-mx-1.5 flex min-h-8 w-[calc(100%+0.75rem)] items-center justify-between gap-2 rounded-lg px-1.5 text-left text-[13px] font-medium text-[var(--muted)] hover:bg-[var(--border)]/40 hover:text-[var(--text)] focus-visible:outline-2 focus-visible:outline-[var(--primary)]"
                    >
                        <span>{summary}</span>
                        <ChevronDown size={16} className={`shrink-0 transition-transform motion-reduce:transition-none ${stepsOpen ? "rotate-180" : ""}`} aria-hidden />
                    </button>
                    {stepsOpen && <div className="mt-2"><TraceView steps={steps} /></div>}
                </div>
            )}
            {isUser ? message.message : <Markdown source={message.message} links={message.links && message.invoices ? { ...message.links, invoices: message.invoices } : undefined} />}
            {message.table && message.links && (
                <InvoiceTable table={message.table} opening={message.links.opening} onOpen={message.links.onOpen} onPay={message.onPay ? () => message.onPay?.() : undefined} />
            )}
            {message.proposal && <PaymentProposalCard proposal={message.proposal} onReview={message.onPay} />}
        </div>
    )
}

import { parseMarkdown, type Inline } from "../../lib/miniMarkdown.js"
import type { InvoiceRef } from "../../api/types.js"
import InvoiceChip from "./InvoiceChip.js"

const INVOICE_ID = /(INV2-[A-Z0-9]{4}(?:-[A-Z0-9]{4}){3})/

export type InvoiceLinks = { invoices: InvoiceRef[]; opening: string | null; onOpen: (invoice: InvoiceRef) => void }

// Plain text in which the ids of known invoices become readable links; any other text is left as it is.
function Text({ text, links }: { text: string; links?: InvoiceLinks }) {
    if (!links || links.invoices.length === 0) return <>{text}</>
    return (
        <>
            {text.split(INVOICE_ID).map((part, i) => {
                const invoice = links.invoices.find(x => x.id === part)
                return invoice
                    ? <InvoiceChip key={i} invoice={invoice} busy={links.opening === invoice.id} onOpen={links.onOpen} />
                    : <span key={i}>{part}</span>
            })}
        </>
    )
}

function Inlines({ parts, links }: { parts: Inline[]; links?: InvoiceLinks }) {
    return (
        <>
            {parts.map((p, i) => {
                if (p.kind === "bold") return <strong key={i} className="font-semibold">{p.text}</strong>
                if (p.kind === "italic") return <em key={i}>{p.text}</em>
                if (p.kind === "code") return <code key={i} className="rounded bg-[var(--border)] px-1 py-0.5 text-[0.85em] break-all">{p.text}</code>
                return <span key={i}><Text text={p.text} links={links} /></span>
            })}
        </>
    )
}

// A reply from the model, shown as formatted text. Only React elements are produced, never HTML from the text.
export default function Markdown({ source, links }: { source: string; links?: InvoiceLinks }) {
    return (
        <div className="space-y-2 break-words [overflow-wrap:anywhere]">
            {parseMarkdown(source).map((block, i) => {
                if (block.kind === "heading") return <p key={i} className="font-semibold"><Inlines parts={block.content} links={links} /></p>
                if (block.kind === "list") {
                    const List = block.ordered ? "ol" : "ul"
                    return (
                        <List key={i} className={`space-y-1 pl-5 ${block.ordered ? "list-decimal" : "list-disc"}`}>
                            {block.items.map((item, j) => <li key={j}><Inlines parts={item} links={links} /></li>)}
                        </List>
                    )
                }
                return (
                    <p key={i}>
                        {block.lines.map((line, j) => <span key={j}>{j > 0 && <br />}<Inlines parts={line} links={links} /></span>)}
                    </p>
                )
            })}
        </div>
    )
}

// A small, safe reader for the Markdown that chat models tend to produce. It returns plain data, never HTML, so the
// text of an invoice that the model repeats can not inject markup. Supported: paragraphs, headings (shown as bold
// lines), bulleted and numbered lists, **bold**, *italic*, `code`, links (shown as their text) and simple tables
// (shown as lines). Anything else stays as ordinary text.

export type Inline = { kind: "text" | "bold" | "italic" | "code"; text: string }
export type Block =
    | { kind: "paragraph"; lines: Inline[][] }
    | { kind: "heading"; content: Inline[] }
    | { kind: "list"; ordered: boolean; items: Inline[][] }

const TOKEN = /(\*\*[^*\n]+\*\*|`[^`\n]+`|\*[^\s*][^*\n]*?\*)/g

export function parseInline(raw: string): Inline[] {
    const text = raw.replace(/\[([^\]\n]+)\]\((?:[^)\s]*)\)/g, "$1")  // [label](url) -> label
    const out: Inline[] = []
    for (const part of text.split(TOKEN)) {
        if (!part) continue
        if (part.startsWith("**") && part.endsWith("**") && part.length > 4) out.push({ kind: "bold", text: part.slice(2, -2) })
        else if (part.startsWith("`") && part.endsWith("`") && part.length > 2) out.push({ kind: "code", text: part.slice(1, -1) })
        else if (part.startsWith("*") && part.endsWith("*") && part.length > 2) out.push({ kind: "italic", text: part.slice(1, -1) })
        else out.push({ kind: "text", text: part })
    }
    return out
}

const BULLET = /^\s*[-*•+]\s+(.*)$/
const NUMBER = /^\s*\d+[.)]\s+(.*)$/
const HEADING = /^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$/
const RULE = /^\s*([-*_]\s*){3,}$/
const TABLE_SEPARATOR = /^\s*\|?[\s:|-]+\|[\s:|-]*$/

export function parseMarkdown(source: string): Block[] {
    const blocks: Block[] = []
    let paragraph: Inline[][] = []
    let list: { ordered: boolean; items: Inline[][] } | null = null
    const flush = () => {
        if (paragraph.length) blocks.push({ kind: "paragraph", lines: paragraph })
        if (list) blocks.push({ kind: "list", ...list })
        paragraph = []
        list = null
    }
    for (const line of source.replace(/\r\n?/g, "\n").replace(/```[a-z]*\n?/gi, "").split("\n")) {
        if (!line.trim() || RULE.test(line) || TABLE_SEPARATOR.test(line)) { flush(); continue }
        const heading = HEADING.exec(line)
        if (heading) { flush(); blocks.push({ kind: "heading", content: parseInline(heading[1]) }); continue }
        const bullet = BULLET.exec(line)
        const number = bullet ? null : NUMBER.exec(line)
        const item = bullet ?? number
        if (item) {
            const ordered = number !== null
            if (list && list.ordered !== ordered) flush()
            if (paragraph.length) flush()
            list ??= { ordered, items: [] }
            list.items.push(parseInline(item[1]))
            continue
        }
        if (list) flush()
        const row = line.trim().startsWith("|") ? line.trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim()).join(" · ") : line.trim()
        paragraph.push(parseInline(row))
    }
    flush()
    return blocks
}

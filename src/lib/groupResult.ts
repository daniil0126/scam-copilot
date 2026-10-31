import type { ComparisonRow, Finding } from "../api/types.js"

// A finding is one of three kinds, and each is shown apart so that nothing reads as more than it is:
// a sign to look at (high / medium), a check that passed, or a check that could not be done.
export function groupFindings(findings: Finding[]) {
    const flagged = findings.filter(f => !f.skipped && (f.severity === "high" || f.severity === "medium"))
        .sort((a, b) => Number(b.severity === "high") - Number(a.severity === "high"))
    return {
        flagged,
        notChecked: findings.filter(f => f.skipped),
        passed: findings.filter(f => !f.skipped && (f.severity === "ok" || f.severity === "low")),
    }
}

type Group = { title: string; now: string; before: string; rows: ComparisonRow[] }

// Rows name their basis in brackets, "Amount (earlier email)". A row without brackets comes from the history check:
// the same supplier's previous invoice, a different invoice from the one on screen.
const BASES: Record<string, { title: string; now: string; before: string }> = {
    "earlier email": { title: "Against the earlier email of this invoice", now: "This email", before: "Earlier email" },
    "page vs email": { title: "Payer page against the emails of this invoice", now: "Page", before: "Email" },
    "": { title: "Against the previous invoice from this supplier", now: "This invoice", before: "Previous invoice" },
}

export function groupRows(rows: ComparisonRow[]): Group[] {
    const groups = new Map<string, Group>()
    for (const row of rows) {
        const m = /^(.*) \(([^)]+)\)$/.exec(row.field)
        const basis = m && m[2] in BASES ? m[2] : ""
        const group = groups.get(basis) ?? { ...BASES[basis], rows: [] }
        group.rows.push({ ...row, field: m && m[2] in BASES ? m[1] : row.field })
        groups.set(basis, group)
    }
    return [...groups.values()]
}

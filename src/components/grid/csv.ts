// The supplier and notes come from other people: a cell that starts with one of these would be run as a formula
// by a spreadsheet. A leading quote keeps it plain text.
export function csvSafe(value: unknown): string {
    const text = value == null ? "" : typeof value === "string" ? value : JSON.stringify(value)
    return /^[=+\-@\t\r]/.test(text) ? `'${text}` : text
}

export const csvFileName = (name: string) => `scam-copilot-${name}-${new Date().toISOString().slice(0, 10)}.csv`

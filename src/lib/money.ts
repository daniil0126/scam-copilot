// An amount the server sent as text, formatted for the reader; the plain text when it cannot be formatted.
export function money(amount?: string, currency?: string): string | null {
    if (!amount) return null
    const value = Number(amount)
    if (!Number.isFinite(value)) return `${amount} ${currency ?? ""}`.trim()
    try {
        return new Intl.NumberFormat(undefined, { style: "currency", currency: currency ?? "USD" }).format(value)
    } catch {
        return `${amount} ${currency ?? ""}`.trim()
    }
}

// Finds the PayPal invoice id on the current page. Pure on purpose: used by the content script and easy to test.

const FULL_ID = /\bINV2-[A-Z0-9]{4}(?:-[A-Z0-9]{4}){3}\b/
// The customer-facing page keeps the same id in the URL hash without the prefix and dashes: /invoice/p/#DQYCSRTKG4R753XN
const SHORT_ID = /^#?([A-Z0-9]{16})$/

const isPayPalHost = (hostname: string) => hostname === "paypal.com" || hostname.endsWith(".paypal.com")

export function extractPayPalInvoiceId(href: string, pageText = ""): string | null {
    let url: URL
    try {
        url = new URL(href)
    } catch {
        return null
    }
    if (!isPayPalHost(url.hostname)) return null

    const fromUrl = FULL_ID.exec(decodeURIComponent(url.pathname + url.search + url.hash))
    if (fromUrl) return fromUrl[0]

    if (url.pathname.startsWith("/invoice/")) {
        const short = SHORT_ID.exec(url.hash)
        if (short) return `INV2-${short[1].match(/.{4}/g)!.join("-")}`
    }

    return FULL_ID.exec(pageText)?.[0] ?? null
}

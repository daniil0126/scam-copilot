import type { PayPalEmailResponse } from "../api/types.js"

// Asks the content script of the active tab for the PayPal invoice email on it. The HTML is read only when this is called.
export async function getPageEmail(): Promise<PayPalEmailResponse> {
    if (typeof chrome === "undefined" || !chrome.tabs) throw new Error("Open Scam Copilot as the browser extension to read the page.")
    const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true })
    if (tab?.id === undefined) throw new Error("No active tab found.")
    try {
        const res: PayPalEmailResponse | undefined = await chrome.tabs.sendMessage(tab.id, { action: "GET_PAYPAL_EMAIL" })
        return res ?? { html: null }
    } catch (e) {
        // "Receiving end does not exist": no content script in this tab. "Port closed": the script was there and failed.
        const why = e instanceof Error ? e.message : ""
        const url = tab.url ? new URL(tab.url).origin : "unknown page"
        throw new Error(`Cannot read this page (${url}). ${why ? `Chrome says: ${why}. ` : ""}Reload the tab and try again.`)
    }
}

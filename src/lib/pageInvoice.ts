import type { PayPalInvoiceResponse } from "../api/types.js"

// Asks the content script of the active tab for the PayPal invoice on it. The text is read only when this is called.
export async function getPageInvoice(): Promise<PayPalInvoiceResponse | null> {
    if (typeof chrome === "undefined" || !chrome.tabs) throw new Error("Open Scam Copilot as the browser extension to read the page.")
    const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true })
    if (tab?.id === undefined) throw new Error("No active tab found.")
    try {
        const res: PayPalInvoiceResponse | undefined = await chrome.tabs.sendMessage(tab.id, { action: "GET_PAYPAL_INVOICE" })
        return res ?? null
    } catch {
        // No content script on this tab: chrome:// pages, the Web Store, or a tab opened before the extension was loaded.
        throw new Error("Cannot read this page. Reload the tab and try again.")
    }
}

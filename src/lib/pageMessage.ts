// Sends a message to the content script of the active tab and returns its answer.
//
// A tab that was open before the extension was installed or reloaded has no content script yet ("Receiving end does not
// exist"), and Chrome does not add one by itself. So when the first try fails, the script is injected and the message is
// sent once more: the user never has to reload the page. Reading still happens only because the user pressed a button.
export class PageReadError extends Error {}

const isPayPalPage = (url: string | undefined) => {
    try {
        const { protocol, hostname } = new URL(url ?? "")
        return protocol === "https:" && (hostname === "paypal.com" || hostname.endsWith(".paypal.com"))
    } catch {
        return false
    }
}

export async function sendToActiveTab<T>(message: { action: string }): Promise<T | undefined> {
    if (typeof chrome === "undefined" || !chrome.tabs) throw new PageReadError("Open Scam Copilot as the browser extension to read the page.")
    const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true })
    if (tab?.id === undefined) throw new PageReadError("No active tab found.")
    if (tab.url && !isPayPalPage(tab.url)) {
        throw new PageReadError("Open a PayPal invoice page or a PayPal invoice email in the active tab, then try again.")
    }
    try {
        return await chrome.tabs.sendMessage<typeof message, T>(tab.id, message)
    } catch {
        try {
            await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content.js"] })
            return await chrome.tabs.sendMessage<typeof message, T>(tab.id, message)
        } catch {
            throw new PageReadError("This page cannot be read right now. Open a PayPal invoice page or email in the active tab and try again.")
        }
    }
}

// Opens PayPal payment pages and says which ones opened. Inside the extension the background worker does it (a burst of tabs
// from a page would be blocked); on the web copy a page can only try window.open, and the browser may allow just the first.
export async function openPayPages(urls: string[]): Promise<boolean[]> {
    if (typeof chrome !== "undefined" && chrome.runtime?.id) {
        try {
            const answer = await chrome.runtime.sendMessage({ action: "OPEN_PAY_TABS", urls }) as { opened?: boolean[] } | undefined
            if (answer?.opened && answer.opened.length === urls.length) return answer.opened
        } catch { /* the worker did not answer: try the page's own way below */ }
    }
    return urls.map(url => {
        const tab = window.open(url, "_blank")
        if (tab) { try { tab.opener = null } catch { /* PayPal's own page; a window that refuses is still fine */ } }
        return tab !== null
    })
}

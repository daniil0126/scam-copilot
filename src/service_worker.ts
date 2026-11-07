import { API_URL, accessHeaders } from "./api/config.js"

// Clicking the toolbar icon opens Chrome's native side panel (src/index.html).
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch((error) => console.error("ERROR: ", error))

// With the panel closed nothing else shows that an alert came in: the toolbar icon carries the unread count.
const ALARM = "unread-alerts"

async function refreshBadge() {
    try {
        const res = await fetch(`${API_URL}/notifications/unread-count`, { headers: accessHeaders() })
        if (!res.ok) return
        const { unread } = await res.json() as { unread: number }
        await chrome.action.setBadgeBackgroundColor({ color: "#e54855" })
        await chrome.action.setBadgeText({ text: unread > 0 ? (unread > 99 ? "99+" : String(unread)) : "" })
    } catch {
        // the backend is not running: leave the badge as it was
    }
}

chrome.alarms.create(ALARM, { periodInMinutes: 0.5 })  // the shortest period Chrome allows
chrome.alarms.onAlarm.addListener(alarm => { if (alarm.name === ALARM) void refreshBadge() })
chrome.runtime.onStartup.addListener(() => void refreshBadge())
chrome.runtime.onInstalled.addListener(() => void refreshBadge())

// "Pay N invoices" opens the PayPal payment pages of the chosen invoices together. A page of the panel opening several tabs is
// blocked by the browser as a burst of pop-ups; the extension's own worker is not. Only PayPal's invoice pages are opened,
// at most ten, and only for a message from this extension.
const PAYMENT_PAGE = /^https:\/\/www\.(sandbox\.)?paypal\.com\/invoice\/p\/#[A-Za-z0-9]{8,40}$/
const MAX_TABS = 10

chrome.runtime.onMessage.addListener((message: { action?: string; urls?: unknown }, sender, sendResponse) => {
    if (message?.action !== "OPEN_PAY_TABS" || sender.id !== chrome.runtime.id) return false
    const urls = (Array.isArray(message.urls) ? message.urls : []).filter((u): u is string => typeof u === "string" && PAYMENT_PAGE.test(u)).slice(0, MAX_TABS)
    void Promise.all(urls.map((url, i) => chrome.tabs.create({ url, active: i === 0 }).then(() => true, () => false)))
        .then(opened => sendResponse({ opened }))
    return true  // the answer comes later
})

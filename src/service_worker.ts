// Clicking the toolbar icon opens Chrome's native side panel (src/index.html).
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch((error) => console.error("ERROR: ", error))

// With the panel closed nothing else shows that an alert came in: the toolbar icon carries the unread count.
const API_URL = "http://localhost:8000"
const ALARM = "unread-alerts"

async function refreshBadge() {
    try {
        const res = await fetch(`${API_URL}/notifications/unread-count`)
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

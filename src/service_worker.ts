// Clicking the toolbar icon toggles the sidebar injected into the active tab.
chrome.action.onClicked.addListener((tab) => {
    if (tab.id === undefined) return
    // Fails on pages where content scripts cannot run (chrome://, the Web Store); nothing to do there.
    chrome.tabs.sendMessage(tab.id, { action: "TOGGLE_SIDEBAR" }).catch(() => { })
})

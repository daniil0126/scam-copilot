// Clicking the toolbar icon opens Chrome's native side panel (src/index.html).
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch((error) => console.error("ERROR: ", error))

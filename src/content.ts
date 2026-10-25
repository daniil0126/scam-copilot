import type { ExtensionMessage } from "./types.js"

chrome.runtime.onMessage.addListener((request: ExtensionMessage, _sender, sendResponse) => {
    // Page content is read only when explicitly requested, never automatically.
    if (request.action === "GET_DOM_STRUCTURE") {
        const rawDOM = document.documentElement.outerHTML
        const domParser = new DOMParser()

        const doc = domParser.parseFromString(rawDOM, "text/html")
        doc.querySelectorAll("svg, script, style, noscript").forEach(el => el.remove())

        sendResponse({ dom: doc.documentElement.outerHTML, url: window.location.href })
    }

    return false
})

import type { ExtensionMessage } from "./types.js"
import { mountOverlay } from "./overlay/mount.js"

const overlay = mountOverlay()

chrome.runtime.onMessage.addListener((request: ExtensionMessage, _sender, sendResponse) => {
    if (request.action === "TOGGLE_SIDEBAR") {
        overlay.toggle()
    }

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

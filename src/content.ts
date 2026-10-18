import { ExtensionMessage } from "./types.js";

chrome.runtime.onMessage.addListener((request: ExtensionMessage, sender, sendResponse) => {
    if(request.action == "GET_DOM_STRUCTURE"){
        const rawDOM = document.documentElement.outerHTML
        const domParser = new DOMParser();

        const doc = domParser.parseFromString(rawDOM, "text/html")
        doc.querySelectorAll("svg, script, style, noscript").forEach(el => el.remove)

        const cleanDOM = doc.documentElement.outerHTML

        sendResponse({dom: cleanDOM, url: window.location.href})
    }

    return true
})


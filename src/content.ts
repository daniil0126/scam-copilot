import type { ExtensionMessage, PayPalEmailResponse, PayPalInvoiceResponse } from "./api/types.js"
import { extractPayPalInvoiceId } from "./lib/paypalPage.js"

const MAX_EMAIL_CHARS = 500_000
const EMAIL_MARKER = /Here['\u2019]s your (updated )?invoice/

// Documents to search: same-origin iframes first (an email preview is usually framed), then the page itself.
function documentsToSearch(root: Document, depth = 0): Document[] {
    const found: Document[] = []
    if (depth < 3) {
        root.querySelectorAll("iframe").forEach(frame => {
            try {
                if (frame.contentDocument) found.push(...documentsToSearch(frame.contentDocument, depth + 1))
            } catch { /* cross-origin frame: not readable, skipped */ }
        })
    }
    found.push(root)
    return found
}

// The email itself, not the page around it: the smallest block that holds both the hidden pre-header and the
// "View ... Invoice" button. Sending the whole page would also send its menus and footer, and the backend would judge those links.
function emailRoot(doc: Document): Element {
    const start = doc.getElementById("preHeader")
    for (let node = start?.parentElement ?? null; node && node !== doc.documentElement; node = node.parentElement) {
        if (Array.from(node.querySelectorAll("a")).some(a => /view.*invoice/i.test(a.textContent ?? ""))) return node
    }
    return doc.documentElement  // the structure is not the usual one: fall back to the whole document
}

// Finds a PayPal invoice email by what it says, not by generated class names.
function findPayPalEmail(): string | null {
    const doc = documentsToSearch(document).find(d => d.getElementById("preHeader") || EMAIL_MARKER.test(d.body?.innerText ?? ""))
    if (!doc) return null
    const copy = new DOMParser().parseFromString(emailRoot(doc).outerHTML, "text/html")
    copy.querySelectorAll("script, style, svg, noscript").forEach(el => el.remove())
    return copy.documentElement.outerHTML.slice(0, MAX_EMAIL_CHARS)
}

chrome.runtime.onMessage.addListener((request: ExtensionMessage, _sender, sendResponse) => {
    // Page content is read only when explicitly requested, never automatically.
    if (request.action === "GET_DOM_STRUCTURE") {
        const rawDOM = document.documentElement.outerHTML
        const domParser = new DOMParser()

        const doc = domParser.parseFromString(rawDOM, "text/html")
        doc.querySelectorAll("svg, script, style, noscript").forEach(el => el.remove())

        sendResponse({ dom: doc.documentElement.outerHTML, url: window.location.href })
    }

    if (request.action === "GET_PAYPAL_INVOICE") {
        const response: PayPalInvoiceResponse = {
            invoiceId: extractPayPalInvoiceId(window.location.href, document.body?.innerText ?? ""),
            url: window.location.href,
            text: (document.body?.innerText ?? "").slice(0, 20_000),
        }
        sendResponse(response)
    }

    if (request.action === "GET_PAYPAL_EMAIL") {
        // Always answer: a handler that throws leaves the side panel with a bare "port closed" and no reason.
        let response: PayPalEmailResponse
        try {
            response = { html: findPayPalEmail() }
        } catch (e) {
            response = { html: null, error: e instanceof Error ? e.message : "unknown error" }
        }
        sendResponse(response)
    }

    return false
})

import { createRoot } from "react-dom/client"
import styles from "../sidepanel/index.css?inline"
import SidebarShell from "../components/sidebar/SidebarShell.js"
import { createOpenStore } from "./store.js"

// Shadow DOM isolates selectors but not units: rem follows the host page's <html> font size.
// Converting to px keeps the panel the same size on every site.
const remToPx = (css: string) => css.replace(/(-?[\d.]+)rem\b/g, (_, n: string) => `${parseFloat(n) * 16}px`)

const HOST_ID = "scam-copilot-root"

// Large but bounded: above typical page UI, below the browser's own limit (2^31 - 1).
const HOST_STYLE = "all: initial; position: fixed; top: 0; left: 0; width: 0; height: 0; z-index: 2147483000;"

export type OverlayHandle = { toggle: () => void }

export function mountOverlay(): OverlayHandle {
    const store = createOpenStore(false)
    const handle: OverlayHandle = { toggle: store.toggle }

    // Only real HTML documents; skips XML, SVG and other non-page documents.
    if (!(document.documentElement instanceof HTMLHtmlElement) || document.getElementById(HOST_ID)) return handle

    // Tailwind registers its custom properties with @property, which only works in the
    // document scope and is ignored inside a shadow root. Registering the same rules on
    // the page keeps transforms, rings and shadows working. They define variables prefixed
    // with --tw-, so they do not affect the page's own styles.
    const propertyRules = styles.match(/@property\s+[^{]+\{[^}]*\}/g)?.join("\n")
    if (propertyRules) {
        const style = document.createElement("style")
        style.textContent = propertyRules
        document.head.appendChild(style)
    }

    const host = document.createElement("div")
    host.id = HOST_ID
    host.setAttribute("style", HOST_STYLE)
    const shadow = host.attachShadow({ mode: "open" })

    const style = document.createElement("style")
    style.textContent = remToPx(styles)
    const container = document.createElement("div")
    shadow.append(style, container)

    createRoot(container).render(<SidebarShell store={store} />)
    document.documentElement.appendChild(host)
    return handle
}

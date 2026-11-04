import SidebarShell from "../components/sidebar/SidebarShell.js"
import { isExtension } from "../api/config.js"
import { createOpenStore } from "../overlay/store.js"

const store = createOpenStore(true)

export default function App() {
    if (isExtension) {
        return (
            <div>
                <SidebarShell store={store} fill />
            </div>
        )
    }
    // The web copy: the side panel as a centred column. The transform makes the panel's fixed positioning relative to this column.
    return (
        <div style={{ minHeight: "100vh", background: "#e8ebf0" }}>
            <div style={{ position: "relative", maxWidth: 560, margin: "0 auto", height: "100vh", transform: "translateZ(0)", boxShadow: "0 0 40px rgba(0,0,0,.18)" }}>
                <SidebarShell store={store} fill />
            </div>
        </div>
    )
}

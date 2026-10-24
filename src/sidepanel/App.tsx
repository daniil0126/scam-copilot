import { useSyncExternalStore } from "react"
import BrowserMock from "../components/browser/BrowserMock.js"
import SidebarShell from "../components/sidebar/SidebarShell.js"
import { createOpenStore } from "../overlay/store.js"

// Development page. The mock browser around the sidebar is switched off for now;
// set this to true to bring it back.
const SHOW_BROWSER_MOCK = false

const store = createOpenStore(true)

export default function App() {
    const open = useSyncExternalStore(store.subscribe, store.get)
    return (
        <>
            {SHOW_BROWSER_MOCK && <BrowserMock onToggleSidebar={store.toggle} />}
            {!SHOW_BROWSER_MOCK && !open && (
                <button onClick={store.toggle} className="m-4 rounded-lg border border-slate-300 px-3 py-2 text-sm">
                    Open Scam Copilot
                </button>
            )}
            <SidebarShell store={store} />
        </>
    )
}

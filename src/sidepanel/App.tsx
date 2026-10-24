import BrowserMock from "../components/browser/BrowserMock.js"
import SidebarShell from "../components/sidebar/SidebarShell.js"
import { createOpenStore } from "../overlay/store.js"

// Development page. The mock browser around the sidebar is switched off for now;
// set this to true to bring it back.
const SHOW_BROWSER_MOCK = false

const store = createOpenStore(true)

export default function App() {
    return (
        <div>
            {SHOW_BROWSER_MOCK && <BrowserMock onToggleSidebar={store.toggle} />}
            <SidebarShell store={store} fill={!SHOW_BROWSER_MOCK} />
        </div>
    )
}

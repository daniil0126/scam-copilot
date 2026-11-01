import SidebarShell from "../components/sidebar/SidebarShell.js"
import { createOpenStore } from "../overlay/store.js"

const store = createOpenStore(true)

export default function App() {
    return (
        <div>
            <SidebarShell store={store} fill />
        </div>
    )
}

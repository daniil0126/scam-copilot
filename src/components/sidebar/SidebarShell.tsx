import { useEffect, useRef, useState, useSyncExternalStore, type KeyboardEvent } from "react"
import type { TabId } from "../../types.js"
import type { OpenStore } from "../../overlay/store.js"
import { useSettings } from "../../overlay/useSettings.js"
import SidebarHeader from "./SidebarHeader.js"
import SidebarTabs from "./SidebarTabs.js"
import FloatingCollapsedTab from "./FloatingCollapsedTab.js"
import CheckTab from "../check/CheckTab.js"
import HistoryView from "../history/HistoryView.js"
import SettingsView from "../settings/SettingsView.js"

// Full class names only: Tailwind cannot detect names built from fragments.
const POSITION_CLASSES = {
    right: { shown: "right-0 translate-x-0 border-l", hidden: "right-0 translate-x-full invisible border-l" },
    left: { shown: "left-0 translate-x-0 border-r", hidden: "left-0 -translate-x-full invisible border-r" },
}

export default function SidebarShell({ store }: { store: OpenStore }) {
    const open = useSyncExternalStore(store.subscribe, store.get)
    const { settings, update } = useSettings()
    const [tab, setTab] = useState<TabId>("check")

    const panelRef = useRef<HTMLElement>(null)
    const restoreFocusTo = useRef<Element | null>(null)
    const wasExpanded = useRef(false)

    const expanded = open && !settings.collapsed

    // The theme goes on the shadow host when injected, so the host page's <html> is never touched.
    useEffect(() => {
        const root = panelRef.current?.getRootNode()
        const target = root instanceof ShadowRoot ? (root.host as HTMLElement) : document.documentElement
        target.dataset.theme = settings.theme
    }, [settings.theme])

    useEffect(() => {
        if (expanded === wasExpanded.current) return
        wasExpanded.current = expanded
        if (expanded) {
            restoreFocusTo.current = document.activeElement
            panelRef.current?.focus({ preventScroll: true })
        } else {
            const previous = restoreFocusTo.current
            restoreFocusTo.current = null
            if (previous instanceof HTMLElement && previous.isConnected) previous.focus({ preventScroll: true })
        }
    }, [expanded])

    const onKeyDown = (e: KeyboardEvent) => {
        if (e.key === "Escape") store.set(false)
    }

    const classes = POSITION_CLASSES[settings.position][expanded ? "shown" : "hidden"]

    return (
        <div className="sc-root">
            <aside
                ref={panelRef}
                tabIndex={-1}
                inert={!expanded}
                aria-label="Scam Copilot"
                onKeyDown={onKeyDown}
                style={{ width: `min(${settings.width}px, 100vw)` }}
                className={`fixed top-0 bottom-0 z-[1] flex flex-col border-[var(--border)] bg-[var(--bg)] text-[var(--text)] shadow-2xl outline-none transition-[transform,visibility] duration-200 ease-out motion-reduce:transition-none ${classes}`}
            >
                <SidebarHeader onOpenSettings={() => setTab("settings")} onClose={() => store.set(false)} />
                <SidebarTabs tab={tab} onChange={setTab} />
                <main role="tabpanel" className="min-h-0 flex-1 overflow-y-auto">
                    {/* Kept mounted so the analysis result survives tab switches. */}
                    <div hidden={tab !== "check"}><CheckTab /></div>
                    {tab === "history" && <HistoryView />}
                    {tab === "settings" && <SettingsView settings={settings} onChange={update} />}
                </main>
            </aside>

            {open && settings.collapsed && (
                <FloatingCollapsedTab position={settings.position} onExpand={() => update({ collapsed: false })} />
            )}
        </div>
    )
}

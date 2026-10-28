import { useEffect, useRef, useState, useSyncExternalStore, type KeyboardEvent } from "react"
import type { TabId } from "../../api/types.js"
import type { OpenStore } from "../../overlay/store.js"
import { useSettings } from "../../overlay/useSettings.js"
import SidebarHeader from "./SidebarHeader.js"
import SidebarTabs from "./SidebarTabs.js"
import ResizeHandle from "./ResizeHandle.js"
import FloatingCollapsedTab from "./FloatingCollapsedTab.js"
import CheckTab from "../check/CheckTab.js"
import ChatTab from "../chat/ChatTab.js"
import HistoryView from "../history/HistoryView.js"
import SettingsView from "../settings/SettingsView.js"

// Full class names only: Tailwind cannot detect names built from fragments.
const SHOWN = "translate-x-0"
const HIDDEN = "translate-x-full invisible"

type Props = {
    store: OpenStore
    // Development page only: fill the whole window instead of floating over a site.
    fill?: boolean
}

export default function SidebarShell({ store, fill = false }: Props) {
    const open = useSyncExternalStore(store.subscribe, store.get)
    const { settings, update } = useSettings()
    const [tab, setTab] = useState<TabId>("check")

    const panelRef = useRef<HTMLElement>(null)
    const restoreFocusTo = useRef<Element | null>(null)
    const wasExpanded = useRef(false)

    const expanded = open && (fill || !settings.collapsed)

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
        if (e.key === "Escape" && !fill) store.set(false)
    }

    const classes = expanded ? SHOWN : HIDDEN

    return (
        <div className="sc-root">
            <aside
                ref={panelRef}
                tabIndex={-1}
                inert={!expanded}
                aria-label="Scam Copilot"
                onKeyDown={onKeyDown}
                style={{ width: fill ? "100vw" : `min(${settings.width}px, 100vw)` }}
                className={`fixed top-0 right-0 bottom-0 z-[1] flex flex-col bg-[var(--bg)] text-[var(--text)] outline-none ${fill ? "" : "border-l border-[var(--border)] shadow-2xl"} transition-[transform,visibility] duration-200 ease-out motion-reduce:transition-none ${classes}`}
            >
                {!fill && <ResizeHandle width={settings.width} onResize={(width) => update({ width })} />}
                <SidebarHeader onOpenSettings={() => setTab("settings")} onClose={fill ? undefined : () => store.set(false)} />
                <SidebarTabs tab={tab} onChange={setTab} />
                <main role="tabpanel" className="min-h-0 flex-1 overflow-y-auto">
                    {/* Kept mounted so the analysis result survives tab switches. */}
                    <div hidden={tab !== "check"}><CheckTab /></div>
                    {/* Kept mounted so the conversation survives tab switches. */}
                    <div className={tab === "chat" ? "h-full" : "hidden"}><ChatTab /></div>
                    {tab === "history" && <HistoryView settings={settings} />}
                    {tab === "settings" && <SettingsView settings={settings} onChange={update} />}
                </main>
            </aside>

            {!fill && open && settings.collapsed && (
                <FloatingCollapsedTab onExpand={() => update({ collapsed: false })} />
            )}
        </div>
    )
}

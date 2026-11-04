import { useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore, type KeyboardEvent } from "react"
import type { InvoiceRef, MonitorSection, TabId } from "../../api/types.js"
import { checkPayPalInvoice } from "../../api/client.js"
import type { OpenStore } from "../../overlay/store.js"
import { useSettings } from "../../overlay/useSettings.js"
import SidebarHeader from "./SidebarHeader.js"
import SidebarTabs, { type TabBadge } from "./SidebarTabs.js"
import ResizeHandle from "./ResizeHandle.js"
import FloatingCollapsedTab from "./FloatingCollapsedTab.js"
import CheckTab from "../check/CheckTab.js"
import ChatTab from "../chat/ChatTab.js"
import HistoryView from "../history/HistoryView.js"
import MonitorTab from "../monitoring/MonitorTab.js"
import { useUnreadCount } from "../alerts/useUnreadCount.js"
import { useAlertArrival } from "../alerts/useAlertArrival.js"
import AlertToast from "../alerts/AlertToast.js"
import { eventKey } from "../monitoring/monitoringMeta.js"
import MonitorStatusChip from "../monitoring/MonitorStatusChip.js"
import { useMonitoring } from "../monitoring/useMonitoring.js"
import SettingsView from "../settings/SettingsView.js"

// Full class names only: Tailwind cannot detect names built from fragments.
const SHOWN = "translate-x-0"
const HIDDEN = "translate-x-full invisible"

type Props = {
    store: OpenStore
    // Development page only: fill the whole window instead of floating over a site.
    fill?: boolean
}

// Where "Back" leads from a check opened out of another place: the tab it was opened from, named for the button.
type ReturnPoint = { tab: TabId; label: string }

const SECTION_LABEL: Record<MonitorSection, string> = { overview: "monitor", alerts: "alerts", report: "report" }

export default function SidebarShell({ store, fill = false }: Props) {
    const open = useSyncExternalStore(store.subscribe, store.get)
    const { settings, update } = useSettings()
    const [tab, setTab] = useState<TabId>("check")
    const [shownCheckId, setShownCheckId] = useState<string | null>(null)
    const [historyOpenId, setHistoryOpenId] = useState<string | null>(null)
    const [returnTo, setReturnTo] = useState<ReturnPoint | null>(null)
    // Kept here, not in the Monitor tab, which is rebuilt each time it is shown: coming back lands on the same section.
    const [monitorSection, setMonitorSection] = useState<MonitorSection>("overview")
    // The panel scrolls as one; each tab's position is remembered so that Back returns to the place that was left.
    const mainRef = useRef<HTMLElement>(null)
    const scrollOf = useRef<Partial<Record<TabId, number>>>({})
    const monitoring = useMonitoring()
    const alerts = useUnreadCount()
    // The badge counts what the monitor found after the panel opened or after the Monitor tab was last in view.
    const [seenAt, setSeenAt] = useState(() => new Date().toISOString())
    // Rows newer than this are highlighted on the Monitor tab: what arrived since the tab was last in view, and what arrives while it is.
    const [highlightSince, setHighlightSince] = useState(seenAt)
    const remember = () => { scrollOf.current[tab] = mainRef.current?.scrollTop ?? 0 }
    const changeTab = (next: TabId) => {
        remember()
        setReturnTo(null)  // a tab picked by hand is a fresh start, not a way back
        if (next === "monitor" && tab !== "monitor") setHighlightSince(seenAt)
        if (tab === "monitor" || next === "monitor") setSeenAt(new Date().toISOString())
        if (next !== "history") setHistoryOpenId(null)  // leaving History closes the check that was open in it
        setTab(next)
    }
    const openCheck = (checkId: string, from?: ReturnPoint) => {
        remember()
        setHistoryOpenId(checkId)
        setReturnTo(from && from.tab !== "history" ? from : null)
        setTab("history")
        if (tab === "monitor") setSeenAt(new Date().toISOString())
    }
    const goBack = () => {
        if (returnTo) changeTab(returnTo.tab)
        else setHistoryOpenId(null)
    }
    // Restore the scroll position of the tab that was just shown (the chat keeps its own, in its message list).
    useLayoutEffect(() => {
        const main = mainRef.current
        if (!main) return
        const wanted = scrollOf.current[tab] ?? 0
        main.scrollTop = wanted
        const frame = requestAnimationFrame(() => { main.scrollTop = wanted })  // after content that loads at once has its height
        return () => cancelAnimationFrame(frame)
    }, [tab])
    // From the chat: open the check of an invoice an answer named, running the check first when there is none.
    const openInvoice = async (invoice: InvoiceRef) => {
        const id = invoice.checkId ?? (await checkPayPalInvoice(invoice.id)).id
        openCheck(id, { tab: "chat", label: "chat" })
    }
    const unseen = tab === "monitor" ? [] : (monitoring.status?.recentEvents ?? []).filter(e => e.detectedAt > seenAt)
    // The server's unread alerts when it can be asked, otherwise what the monitor found since the panel opened.
    const alertsKnown = alerts.error === null
    const badges: Partial<Record<TabId, TabBadge>> = settings.notifications ? {
        monitor: alertsKnown
            ? { count: alerts.unread, urgent: false }
            : { count: unseen.length, urgent: unseen.some(e => e.riskLevel === "high") },
    } : {}

    const arrival = useAlertArrival(alerts.unread, alerts.error === null, settings.notifications)
    const openArrival = () => {
        arrival.dismiss()
        setMonitorSection("alerts")
        changeTab("monitor")
    }

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
                style={{ width: fill ? "100%" : `min(${settings.width}px, 100vw)` }}
                className={`fixed top-0 right-0 bottom-0 z-[1] flex flex-col bg-[var(--bg)] text-[var(--text)] outline-none ${fill ? "" : "border-l border-[var(--border)] shadow-2xl"} transition-[transform,visibility] duration-200 ease-out motion-reduce:transition-none ${classes}`}
            >
                {!fill && <ResizeHandle width={settings.width} onResize={(width) => update({ width })} />}
                <SidebarHeader
                    status={<MonitorStatusChip status={monitoring.status} onClick={() => changeTab("monitor")} />}
                    onOpenSettings={() => changeTab("settings")}
                    onClose={fill ? undefined : () => store.set(false)} />
                <SidebarTabs tab={tab} onChange={changeTab} badges={badges} />
                {/* A new key remounts the overlay, which plays the flash again for each arrival. */}
                {arrival.flashKey > 0 && <div key={arrival.flashKey} aria-hidden className="sc-alert-flash pointer-events-none absolute inset-0 z-20" />}
                {arrival.arrival && <AlertToast alert={arrival.arrival} onOpen={openArrival} onDismiss={arrival.dismiss} />}
                <main ref={mainRef} role="tabpanel" className="min-h-0 flex-1 overflow-y-auto">
                    {/* Kept mounted so the analysis result survives tab switches. */}
                    <div hidden={tab !== "check"}><CheckTab onOpenHistory={() => changeTab("history")} onShownChange={setShownCheckId} /></div>
                    {/* Kept mounted so the conversation survives tab switches. */}
                    <div className={tab === "chat" ? "h-full" : "hidden"}><ChatTab checkId={shownCheckId} onOpenInvoice={openInvoice} active={tab === "chat"} /></div>
                    {tab === "monitor" && (
                        <MonitorTab
                            monitoring={monitoring} alerts={alerts} highlightSince={highlightSince}
                            section={monitorSection} onSectionChange={setMonitorSection}
                            onOpenCheck={id => openCheck(id, { tab: "monitor", label: SECTION_LABEL[monitorSection] })}
                        />
                    )}
                    {tab === "history" && <HistoryView settings={settings} reloadKey={eventKey(monitoring.status?.recentEvents[0])} openId={historyOpenId} onOpenChange={setHistoryOpenId} backLabel={returnTo?.label} onBack={returnTo ? goBack : undefined} />}
                    {tab === "settings" && <SettingsView settings={settings} onChange={update} />}
                </main>
            </aside>

            {!fill && open && settings.collapsed && (
                <FloatingCollapsedTab onExpand={() => update({ collapsed: false })} />
            )}
        </div>
    )
}

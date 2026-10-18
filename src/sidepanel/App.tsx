import { useEffect, useState } from "react"
import { ShieldCheck } from "lucide-react"
import { TabId, UserSettings } from "../types.js"
import { DEFAULT_SETTINGS, loadSettings, saveSettings } from "../lib/settings.js"
import ChatWidget from "../components/ChatWidget.js"
import SettingsView from "../components/settings/SettingsView.js"

const TABS: { id: TabId, label: string }[] = [
    { id: "check", label: "Check" },
    { id: "history", label: "History" },
    { id: "settings", label: "Settings" },
]

export default function App() {
    const [tab, setTab] = useState<TabId>("check")
    const [settings, setSettings] = useState<UserSettings>(DEFAULT_SETTINGS)

    useEffect(() => {
        loadSettings().then(setSettings)
    }, [])

    useEffect(() => {
        document.documentElement.dataset.theme = settings.theme
    }, [settings.theme])

    const updateSettings = (patch: Partial<UserSettings>) => {
        const next = { ...settings, ...patch }
        setSettings(next)
        saveSettings(next)
    }

    return (
        <div className="flex h-screen flex-col bg-[var(--bg)] text-[var(--text)]">
            <header className="flex items-center gap-2 bg-[var(--navy)] px-4 py-3 text-white">
                <ShieldCheck size={20} />
                <h1 className="text-base font-semibold">Scam Copilot</h1>
            </header>

            <nav role="tablist" className="flex border-b border-[var(--border)] bg-[var(--card)]">
                {TABS.map(({ id, label }) => {
                    const active = tab === id
                    return (
                        <button
                            key={id}
                            role="tab"
                            aria-selected={active}
                            onClick={() => setTab(id)}
                            className={`flex-1 border-b-2 px-2 py-3 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--primary)] ${active
                                ? "border-[var(--primary)] text-[var(--primary)]"
                                : "border-transparent text-[var(--muted)] hover:text-[var(--text)]"}`}
                        >
                            {label}
                        </button>
                    )
                })}
            </nav>

            <main role="tabpanel" className="flex-1 overflow-y-auto">
                {tab === "settings" && <SettingsView settings={settings} onChange={updateSettings} />}
            </main>

            <ChatWidget />
        </div>
    )
}

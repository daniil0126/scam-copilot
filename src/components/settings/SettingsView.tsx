import { Moon, Sun } from "lucide-react"
import { Theme, UserSettings } from "../../types.js"

type Props = {
    settings: UserSettings
    onChange: (patch: Partial<UserSettings>) => void
}

function Section({ title, children }: { title: string, children: React.ReactNode }) {
    return (
        <section className="mb-5">
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">{title}</h2>
            {children}
        </section>
    )
}

const THEMES: { id: Theme, label: string, icon: typeof Sun }[] = [
    { id: "light", label: "Light", icon: Sun },
    { id: "dark", label: "Dark", icon: Moon },
]

export default function SettingsView({ settings, onChange }: Props) {
    return (
        <div className="p-4">
            <Section title="Appearance">
                <div role="radiogroup" aria-label="Theme" className="grid grid-cols-2 gap-2">
                    {THEMES.map(({ id, label, icon: Icon }) => {
                        const active = settings.theme === id
                        return (
                            <button
                                key={id}
                                role="radio"
                                aria-checked={active}
                                onClick={() => onChange({ theme: id })}
                                className={`flex items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-[var(--primary)] active:scale-[0.98] ${active
                                    ? "border-[var(--primary)] bg-[var(--primary-soft)] text-[var(--primary)]"
                                    : "border-[var(--border)] bg-[var(--card)] text-[var(--text)] hover:bg-[var(--primary-soft)]"}`}
                            >
                                <Icon size={16} /> {label}
                            </button>
                        )
                    })}
                </div>
            </Section>

            <Section title="Notifications">
                <label className="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-3">
                    <span className="text-sm text-[var(--text)]">Show risk notifications</span>
                    <input
                        type="checkbox"
                        role="switch"
                        checked={settings.notifications}
                        onChange={(e) => onChange({ notifications: e.target.checked })}
                        className="peer sr-only"
                    />
                    <span className="relative h-6 w-10 shrink-0 rounded-full bg-[var(--border)] transition-colors after:absolute after:left-0.5 after:top-0.5 after:h-5 after:w-5 after:rounded-full after:bg-white after:shadow after:transition-transform peer-checked:bg-[var(--primary)] peer-checked:after:translate-x-4 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-[var(--primary)]" />
                </label>
            </Section>
        </div>
    )
}

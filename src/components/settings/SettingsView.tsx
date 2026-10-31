import { useEffect, useState, type ReactNode } from "react"
import { Moon, Sun, type LucideIcon } from "lucide-react"
import type { Theme, UserSettings } from "../../api/types.js"
import { loadInboundSecret, saveInboundSecret } from "../../lib/inboundSecret.js"

type Props = {
    settings: UserSettings
    onChange: (patch: Partial<UserSettings>) => void
}

function Section({ title, children }: { title: string, children: ReactNode }) {
    return (
        <section className="mb-5">
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">{title}</h2>
            {children}
        </section>
    )
}

type Option<T extends string> = { id: T, label: string, icon: LucideIcon }

function OptionGroup<T extends string>({ label, value, options, onChange }: {
    label: string
    value: T
    options: Option<T>[]
    onChange: (value: T) => void
}) {
    return (
        <div role="radiogroup" aria-label={label} className="grid grid-cols-2 gap-2">
            {options.map(({ id, label: text, icon: Icon }) => {
                const active = value === id
                return (
                    <button
                        key={id}
                        role="radio"
                        aria-checked={active}
                        onClick={() => onChange(id)}
                        className={`flex items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-[var(--primary)] active:scale-[0.98] ${active
                            ? "border-[var(--primary)] bg-[var(--primary-soft)] text-[var(--primary)]"
                            : "border-[var(--border)] bg-[var(--card)] text-[var(--text)] hover:bg-[var(--primary-soft)]"}`}
                    >
                        <Icon size={16} aria-hidden /> {text}
                    </button>
                )
            })}
        </div>
    )
}

function Toggle({ label, checked, onChange }: { label: string, checked: boolean, onChange: (checked: boolean) => void }) {
    return (
        <label className="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-3">
            <span className="text-sm text-[var(--text)]">{label}</span>
            <input
                type="checkbox"
                role="switch"
                checked={checked}
                onChange={(e) => onChange(e.target.checked)}
                className="peer sr-only"
            />
            <span className="relative h-6 w-10 shrink-0 rounded-full bg-[var(--border)] transition-colors after:absolute after:left-0.5 after:top-0.5 after:h-5 after:w-5 after:rounded-full after:bg-white after:shadow after:transition-transform peer-checked:bg-[var(--primary)] peer-checked:after:translate-x-4 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-[var(--primary)]" />
        </label>
    )
}

const THEMES: Option<Theme>[] = [
    { id: "light", label: "Light", icon: Sun },
    { id: "dark", label: "Dark", icon: Moon },
]

export default function SettingsView({ settings, onChange }: Props) {
    const [secret, setSecret] = useState("")
    useEffect(() => { void loadInboundSecret().then(setSecret) }, [])

    return (
        <div className="p-4">
            <Section title="Appearance">
                <OptionGroup label="Theme" value={settings.theme} options={THEMES} onChange={theme => onChange({ theme })} />
            </Section>

            <Section title="Collapsed mode">
                <Toggle label="Collapse to a floating tab" checked={settings.collapsed} onChange={collapsed => onChange({ collapsed })} />
            </Section>

            <Section title="Email checks">
                <label className="block text-sm text-[var(--text)]">
                    Inbound secret
                    <input
                        type="password"
                        autoComplete="off"
                        value={secret}
                        onChange={(e) => { setSecret(e.target.value); void saveInboundSecret(e.target.value) }}
                        className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-[var(--primary)]"
                    />
                </label>
                <p className="mt-1 text-[11px] leading-snug text-[var(--muted)]">
                    Must match INBOUND_EMAIL_SECRET on the server. Stored only in this browser.
                </p>
            </Section>

            <Section title="Notifications">
                <Toggle label="Show risk notifications" checked={settings.notifications} onChange={notifications => onChange({ notifications })} />
            </Section>
        </div>
    )
}

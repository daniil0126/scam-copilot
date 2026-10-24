import type { ReactNode } from "react"
import { Moon, PanelLeft, PanelRight, Sun, type LucideIcon } from "lucide-react"
import type { SidebarPosition, Theme, UserSettings } from "../../types.js"
import { MAX_WIDTH, MIN_WIDTH } from "../../lib/settings.js"

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

const POSITIONS: Option<SidebarPosition>[] = [
    { id: "right", label: "Right", icon: PanelRight },
    { id: "left", label: "Left", icon: PanelLeft },
]

export default function SettingsView({ settings, onChange }: Props) {
    return (
        <div className="p-4">
            <Section title="Appearance">
                <OptionGroup label="Theme" value={settings.theme} options={THEMES} onChange={theme => onChange({ theme })} />
            </Section>

            <Section title="Sidebar position">
                <OptionGroup label="Sidebar position" value={settings.position} options={POSITIONS} onChange={position => onChange({ position })} />
            </Section>

            <Section title="Sidebar width">
                <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-3">
                    <div className="mb-2 flex justify-between text-sm">
                        <label htmlFor="sc-width">Width</label>
                        <span className="font-semibold text-[var(--primary)]">{settings.width}px</span>
                    </div>
                    <input
                        id="sc-width"
                        type="range"
                        min={MIN_WIDTH}
                        max={MAX_WIDTH}
                        step={10}
                        value={settings.width}
                        aria-valuetext={`${settings.width} pixels`}
                        onChange={(e) => onChange({ width: Number(e.target.value) })}
                        className="w-full accent-[var(--primary)]"
                    />
                    <div className="mt-1 flex justify-between text-[11px] text-[var(--muted)]">
                        <span>{MIN_WIDTH}px</span><span>{MAX_WIDTH}px</span>
                    </div>
                </div>
            </Section>

            <Section title="Collapsed mode">
                <Toggle label="Collapse to a floating tab" checked={settings.collapsed} onChange={collapsed => onChange({ collapsed })} />
            </Section>

            <Section title="Notifications">
                <Toggle label="Show risk notifications" checked={settings.notifications} onChange={notifications => onChange({ notifications })} />
            </Section>
        </div>
    )
}

import { Settings, ShieldCheck, X } from "lucide-react"

type Props = {
    onOpenSettings: () => void
    onClose?: () => void
}

const ICON_BUTTON = "rounded-md p-1.5 text-white/80 transition hover:bg-white/10 hover:text-white active:scale-95 focus-visible:outline-2 focus-visible:outline-white"

export default function SidebarHeader({ onOpenSettings, onClose }: Props) {
    return (
        <header className="flex items-center gap-2 bg-[var(--navy)] px-4 py-3 text-white">
            <ShieldCheck size={20} aria-hidden />
            <h1 className="flex-1 text-base font-semibold">Scam Copilot</h1>
            <button aria-label="Open settings" onClick={onOpenSettings} className={ICON_BUTTON}><Settings size={18} /></button>
            {onClose && <button aria-label="Close Scam Copilot" onClick={onClose} className={ICON_BUTTON}><X size={18} /></button>}
        </header>
    )
}

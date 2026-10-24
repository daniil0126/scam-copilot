import { ShieldCheck } from "lucide-react"
import type { SidebarPosition } from "../../types.js"

type Props = {
    position: SidebarPosition
    onExpand: () => void
}

export default function FloatingCollapsedTab({ position, onExpand }: Props) {
    const side = position === "right" ? "right-0 rounded-l-xl" : "left-0 rounded-r-xl"
    return (
        <button
            aria-label="Open Scam Copilot"
            onClick={onExpand}
            className={`fixed top-1/3 z-[1] flex h-12 w-10 items-center justify-center bg-[var(--navy)] text-white shadow-lg transition hover:w-12 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)] motion-reduce:transition-none ${side}`}
        >
            <ShieldCheck size={20} aria-hidden />
        </button>
    )
}

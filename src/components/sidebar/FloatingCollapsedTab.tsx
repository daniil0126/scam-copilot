import { ShieldCheck } from "lucide-react"
type Props = {
    onExpand: () => void
}

export default function FloatingCollapsedTab({ onExpand }: Props) {
    return (
        <button
            aria-label="Open Scam Copilot"
            onClick={onExpand}
            className="fixed top-1/3 right-0 z-[1] rounded-l-xl flex h-12 w-10 items-center justify-center bg-[var(--navy)] text-white shadow-lg transition hover:w-12 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)] motion-reduce:transition-none"
        >
            <ShieldCheck size={20} aria-hidden />
        </button>
    )
}

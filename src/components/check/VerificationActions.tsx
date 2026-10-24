type Props = {
    detailsOpen: boolean
    onToggleDetails: () => void
    onCheckPayPal: () => void
}

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"

export default function VerificationActions({ detailsOpen, onToggleDetails, onCheckPayPal }: Props) {
    return (
        <div className="flex flex-wrap gap-2">
            <button
                onClick={onToggleDetails}
                aria-expanded={detailsOpen}
                className={`min-w-[8rem] flex-1 rounded-lg border border-[var(--primary)] px-3 py-2.5 text-sm font-semibold text-[var(--primary)] transition hover:bg-[var(--primary-soft)] active:scale-[0.98] ${FOCUS}`}
            >
                {detailsOpen ? "Hide details" : "Show details"}
            </button>
            <button
                onClick={onCheckPayPal}
                className={`min-w-[8rem] flex-1 rounded-lg bg-[var(--primary)] px-3 py-2.5 text-sm font-semibold text-white transition hover:brightness-110 active:scale-[0.98] ${FOCUS}`}
            >
                Check in PayPal
            </button>
        </div>
    )
}

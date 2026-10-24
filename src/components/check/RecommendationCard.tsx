import { Info } from "lucide-react"

export default function RecommendationCard({ text }: { text: string }) {
    return (
        <div className="flex gap-2.5 rounded-xl bg-[var(--primary-soft)] p-3 text-sm text-[var(--text)]">
            <Info size={18} className="mt-0.5 shrink-0 text-[var(--primary)]" aria-hidden />
            <p>{text}</p>
        </div>
    )
}

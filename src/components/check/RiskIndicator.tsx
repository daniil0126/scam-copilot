import type { RiskLevel } from "../../types.js"
import { LEVEL_META } from "../../lib/risk.js"

const R = 26
const C = 2 * Math.PI * R

export default function RiskIndicator({ score, level }: { score: number, level: RiskLevel }) {
    const meta = LEVEL_META[level]
    return (
        <div className="flex flex-col items-center gap-1">
            <div role="img" aria-label={`Risk score ${score}%`} className="relative h-16 w-16">
                <svg viewBox="0 0 64 64" className="h-full w-full -rotate-90">
                    <circle cx="32" cy="32" r={R} fill="none" stroke="var(--border)" strokeWidth="6" />
                    <circle
                        cx="32" cy="32" r={R} fill="none" stroke={meta.stroke} strokeWidth="6" strokeLinecap="round"
                        strokeDasharray={C} strokeDashoffset={C * (1 - score / 100)}
                    />
                </svg>
                <span className={`absolute inset-0 flex items-center justify-center text-base font-bold ${meta.text}`}>{score}%</span>
            </div>
            <span className={`text-xs font-semibold ${meta.text}`}>{meta.label}</span>
        </div>
    )
}

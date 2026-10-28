import { AlertTriangle, CheckCircle2, ShieldAlert, type LucideIcon } from "lucide-react"
import type { FindingSeverity, RiskLevel } from "../api/types.js"

type LevelMeta = {
    label: string
    icon: LucideIcon
    text: string
    soft: string
    border: string
    stroke: string
}

// Full class names only: Tailwind cannot detect names built from fragments.
export const LEVEL_META: Record<RiskLevel, LevelMeta> = {
    high: { label: "High risk", icon: ShieldAlert, text: "text-[var(--danger)]", soft: "bg-[var(--danger-soft)]", border: "border-[var(--danger)]/30", stroke: "var(--danger)" },
    medium: { label: "Medium risk", icon: AlertTriangle, text: "text-[var(--warning)]", soft: "bg-[var(--warning-soft)]", border: "border-[var(--warning)]/30", stroke: "var(--warning)" },
    low: { label: "Low risk", icon: CheckCircle2, text: "text-[var(--success)]", soft: "bg-[var(--success-soft)]", border: "border-[var(--success)]/30", stroke: "var(--success)" },
}

export const SEVERITY_TEXT: Record<FindingSeverity, string> = {
    high: "text-[var(--danger)]",
    medium: "text-[var(--warning)]",
    low: "text-[var(--success)]",
    ok: "text-[var(--success)]",
}

export function alertTitle(level: RiskLevel, findingCount: number): { title: string, subtitle: string } {
    if (level === "low") return { title: "All good", subtitle: "No obvious issues found" }
    const noun = findingCount === 1 ? "risk" : "risks"
    return {
        title: level === "high" ? "Suspicious invoice" : "Needs attention",
        subtitle: `${findingCount} ${noun} found`,
    }
}

export const formatMoney = (amount: number, currency: string) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency }).format(amount)

export const formatDateTime = (iso: string) =>
    new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })

import { AlertTriangle, CheckCircle2, ShieldAlert, type LucideIcon } from "lucide-react"
import type { AlertLevel, FindingSeverity, RiskLevel } from "../api/types.js"

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

// Alerts and reports use four capitalised levels. CRITICAL looks like HIGH with a stronger fill.
export const ALERT_LEVEL_META: Record<AlertLevel, LevelMeta & { solid: string }> = {
    CRITICAL: { ...LEVEL_META.high, label: "Critical risk", solid: "bg-[var(--danger)]" },
    HIGH: { ...LEVEL_META.high, solid: "bg-[var(--danger)]" },
    MEDIUM: { ...LEVEL_META.medium, solid: "bg-[var(--warning)]" },
    LOW: { ...LEVEL_META.low, solid: "bg-[var(--success)]" },
}

export const SEVERITY_TEXT: Record<FindingSeverity, string> = {
    high: "text-[var(--danger)]",
    medium: "text-[var(--warning)]",
    low: "text-[var(--success)]",
    ok: "text-[var(--success)]",
}

// `signCount` counts only the signs to look at: passed and not-checked findings are not "risks found".
export function alertTitle(level: RiskLevel, signCount: number): { title: string, subtitle: string } {
    if (level === "low") return { title: "No obvious issues", subtitle: "Only the available signals were checked" }
    return {
        title: level === "high" ? "Several signs of a suspicious invoice" : "Some signs need attention",
        subtitle: signCount === 1 ? "1 sign to look at" : `${signCount} signs to look at`,
    }
}

export const formatMoney = (amount: number, currency: string) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency }).format(amount)

export const formatDateTime = (iso: string) =>
    new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })

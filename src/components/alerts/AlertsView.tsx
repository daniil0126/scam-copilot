import { useCallback, useEffect, useState } from "react"
import { BellOff, ChevronDown, Loader2 } from "lucide-react"
import { fetchNotifications, markNotificationRead } from "../../api/client.js"
import type { AppNotification } from "../../api/types.js"
import { ALERT_LEVEL_META, formatDateTime, formatMoney } from "../../lib/risk.js"
import { signalLabel } from "../../lib/signals.js"

const PAGE = 20

type Props = {
    // Changes when the unread count does, so a new alert appears without a click.
    reloadKey: number
    onRead: () => void
    // Opens that stored check in History.
    onOpenCheck: (checkId: string) => void
}

function describe(item: AppNotification): string {
    const invoice = item.invoice
    if (!invoice) return "Details unavailable"
    let money = ""
    if (invoice.amount !== null) {
        try {
            money = invoice.currency ? formatMoney(invoice.amount, invoice.currency) : String(invoice.amount)
        } catch {
            money = `${invoice.amount} ${invoice.currency ?? ""}`.trim()  // an unknown currency code
        }
    }
    return [invoice.supplierName ?? "Unknown sender", invoice.number && `#${invoice.number}`, money].filter(Boolean).join(" · ")
}

export default function AlertsView({ reloadKey, onRead, onOpenCheck }: Props) {
    const [items, setItems] = useState<AppNotification[] | null>(null)
    const [nextCursor, setNextCursor] = useState<string | null>(null)
    const [unreadOnly, setUnreadOnly] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [loadingMore, setLoadingMore] = useState(false)
    const [openId, setOpenId] = useState<string | null>(null)

    useEffect(() => {
        let cancelled = false
        fetchNotifications({ unreadOnly, limit: PAGE })
            .then(page => {
                if (cancelled) return
                setItems(page.items)
                setNextCursor(page.nextCursor)
                setError(null)
            })
            .catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : "Could not load alerts.") })
        return () => { cancelled = true }
    }, [unreadOnly, reloadKey])

    const loadMore = async () => {
        if (!nextCursor) return
        setLoadingMore(true)
        try {
            const page = await fetchNotifications({ unreadOnly, limit: PAGE, cursor: nextCursor })
            setItems(current => [...(current ?? []), ...page.items])
            setNextCursor(page.nextCursor)
        } catch (e) {
            setError(e instanceof Error ? e.message : "Could not load more alerts.")
        } finally {
            setLoadingMore(false)
        }
    }

    // Opening an unread alert marks it read. The row changes at once and goes back if the server refuses.
    const open = useCallback(async (item: AppNotification) => {
        setOpenId(id => (id === item.id ? null : item.id))
        if (item.read) return
        setItems(current => current?.map(n => (n.id === item.id ? { ...n, read: true } : n)) ?? null)
        try {
            await markNotificationRead(item.id)
            onRead()
        } catch (e) {
            setItems(current => current?.map(n => (n.id === item.id ? { ...n, read: false } : n)) ?? null)
            setError(e instanceof Error ? e.message : "Could not mark the alert as read.")
        }
    }, [onRead])

    return (
        <section aria-label="Alerts" className="p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
                <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Alerts</h2>
                <label className="flex cursor-pointer items-center gap-1.5 text-xs text-[var(--muted)]">
                    <input type="checkbox" checked={unreadOnly} onChange={e => { setItems(null); setUnreadOnly(e.target.checked) }} />
                    Unread only
                </label>
            </div>

            {error && <p role="alert" className="mb-2 rounded-lg bg-[var(--danger-soft)] px-3 py-2 text-xs font-medium text-[var(--danger)]">{error}</p>}

            {!items && !error && (
                <div role="status" className="flex items-center justify-center gap-2 p-10 text-sm text-[var(--muted)]">
                    <Loader2 size={18} aria-hidden className="motion-safe:animate-spin" /> Loading alerts…
                </div>
            )}

            {items && items.length === 0 && (
                <div className="flex flex-col items-center gap-2 p-10 text-center text-sm text-[var(--muted)]">
                    <BellOff size={28} aria-hidden />
                    {unreadOnly ? "No unread alerts." : "No alerts yet. An alert appears when a checked invoice shows signs worth a look."}
                </div>
            )}

            {items && items.length > 0 && (
                <ul className="flex flex-col gap-2">
                    {items.map(item => {
                        const risk = ALERT_LEVEL_META[item.riskLevel]
                        const expanded = openId === item.id
                        return (
                            <li key={item.id} className="rounded-lg border border-[var(--border)] bg-[var(--card)]">
                                <button
                                    aria-expanded={expanded}
                                    onClick={() => void open(item)}
                                    className="flex w-full cursor-pointer gap-3 p-2.5 text-left focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--primary)]"
                                >
                                    <span aria-hidden className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md ${risk.soft} ${risk.text}`}>
                                        <risk.icon size={15} />
                                    </span>
                                    <span className="min-w-0 flex-1">
                                        <span className="flex items-baseline justify-between gap-2">
                                            <span className={`flex min-w-0 items-center gap-1.5 text-sm ${item.read ? "font-medium" : "font-bold"}`}>
                                                {!item.read && <span aria-label="Unread" className="h-2 w-2 shrink-0 rounded-full bg-[var(--primary)]" />}
                                                <span className="truncate">{item.title}</span>
                                            </span>
                                            <time dateTime={item.detectedAt} className="shrink-0 text-xs tabular-nums text-[var(--muted)]">{formatDateTime(item.detectedAt)}</time>
                                        </span>
                                        <span className="mt-0.5 block truncate text-xs text-[var(--muted)]" title={item.invoiceId}>{describe(item)}</span>
                                        <span className="mt-1.5 flex flex-wrap items-center gap-1.5">
                                            <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${risk.soft} ${risk.text}`}>
                                                <risk.icon size={12} aria-hidden /> {risk.label}
                                            </span>
                                            {item.signals.slice(0, 2).map(signal => (
                                                <span key={signal} className="rounded-full border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--muted)]">{signalLabel(signal)}</span>
                                            ))}
                                            {item.signals.length > 2 && <span className="text-xs text-[var(--muted)]">+{item.signals.length - 2}</span>}
                                        </span>
                                    </span>
                                    <ChevronDown size={14} aria-hidden className={`mt-1 shrink-0 text-[var(--muted)] transition-transform motion-reduce:transition-none ${expanded ? "rotate-180" : ""}`} />
                                </button>
                                {expanded && (
                                    <div className="border-t border-[var(--border)] px-3 py-2.5 text-xs leading-snug">
                                        <p className="[overflow-wrap:anywhere]">{item.message}</p>
                                        {item.invoice ? (
                                            <button
                                                onClick={() => onOpenCheck(item.invoice!.checkId)}
                                                className="mt-2 min-h-8 cursor-pointer rounded-lg border border-[var(--border)] px-3 text-xs font-semibold text-[var(--primary)] hover:bg-[var(--primary-soft)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"
                                            >
                                                Open this check
                                            </button>
                                        ) : (
                                            <p className="mt-2 text-[var(--muted)] [overflow-wrap:anywhere]">
                                                No stored check for this invoice (PayPal id {item.invoiceId}). If the backend was updated, restart it.
                                            </p>
                                        )}
                                    </div>
                                )}
                            </li>
                        )
                    })}
                </ul>
            )}

            {nextCursor && (
                <button
                    onClick={() => void loadMore()}
                    disabled={loadingMore}
                    className="mt-2 inline-flex min-h-8 w-full cursor-pointer items-center justify-center gap-1.5 rounded-lg text-xs font-semibold text-[var(--primary)] hover:bg-[var(--primary-soft)] disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"
                >
                    {loadingMore && <Loader2 size={14} aria-hidden className="motion-safe:animate-spin" />} Load more
                </button>
            )}
        </section>
    )
}

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import {
    cancelPayIntent, checkInvoiceNow, createPayIntents, fetchPayIntentStatus, markPayIntentOpened, previewPayments,
} from "../api/client.js"
import type { PayIntent, PayView } from "../api/types.js"
import { MAX_BASKET, label, plural, sumTotals, totalsText } from "./payFormat.js"
import { openPayPages } from "./openPages.js"
import { PaymentsCtx, type Payments, type PaySource, type QueueItem, type QueueState, type Sheet } from "./context.js"

// Paying means being led to PayPal's own page for an invoice. Nothing here moves money, and nothing here decides who may be
// paid: the server does (backend/app/payments.py), and checks again at the moment of confirming. This holds only what the
// panel shows: the server's verdicts, the ticked invoices, the open confirmation and the payments in progress.

const POLL_MS = 4000
const CHUNK = 50

export function PaymentsProvider({ children }: { children: ReactNode }) {
    const [views, setViews] = useState<Record<string, PayView>>({})
    const [selection, setSelection] = useState<ReadonlySet<string>>(new Set())
    const [checking, setChecking] = useState<ReadonlySet<string>>(new Set())
    const [sheet, setSheet] = useState<Sheet | null>(null)
    const [queue, setQueue] = useState<QueueItem[] | null>(null)
    const [announce, setAnnounce] = useState("")
    const asked = useRef(new Set<string>())
    const sheetOpener = useRef<Element | null>(null)
    const say = useCallback((text: string) => { setAnnounce(""); setTimeout(() => setAnnounce(text), 30) }, [])

    const merge = useCallback((items: PayView[]) => {
        setViews(prev => ({ ...prev, ...Object.fromEntries(items.map(v => [v.invoiceId, v])) }))
    }, [])

    const load = useCallback(async (ids: string[]) => {
        for (let i = 0; i < ids.length; i += CHUNK) {
            try {
                merge((await previewPayments(ids.slice(i, i + CHUNK))).items)
            } catch {
                ids.slice(i, i + CHUNK).forEach(id => asked.current.delete(id))  // asked again next time the list is drawn
            }
        }
    }, [merge])

    const ensure = useCallback((ids: string[]) => {
        const need = [...new Set(ids)].filter(id => !asked.current.has(id))
        need.forEach(id => asked.current.add(id))
        if (need.length) void load(need)
    }, [load])

    // An invoice that can no longer be paid leaves the selection.
    useEffect(() => {
        setSelection(prev => {
            // An invoice the gate has not been asked about yet stays: History asks as soon as it is drawn.
            const keep = [...prev].filter(id => (!views[id] || views[id].eligible) && !inProgressRef.current.has(id))
            return keep.length === prev.size ? prev : new Set(keep)
        })
    }, [views])

    const inProgressRef = useRef(new Set<string>())
    const toggle = useCallback((id: string, on: boolean) => {
        setSelection(prev => { const next = new Set(prev); if (on) next.add(id); else next.delete(id); return next })
    }, [])
    const setMany = useCallback((ids: string[], on: boolean) => {
        setSelection(prev => { const next = new Set(prev); ids.forEach(id => (on ? next.add(id) : next.delete(id))); return next })
    }, [])
    const clearSelection = useCallback(() => setSelection(new Set()), [])

    const checkNow = useCallback(async (id: string) => {
        setChecking(prev => new Set(prev).add(id))
        try {
            const view = await checkInvoiceNow(id)
            merge([view])
            say(view.eligible ? `${label(view)}: no warning signs found. You can pay it now.` : `${label(view)}: ${view.reasons[0]?.text ?? "cannot be paid from here"}.`)
        } catch (e) {
            say(e instanceof Error ? e.message : "Could not check this invoice.")
        } finally {
            setChecking(prev => { const next = new Set(prev); next.delete(id); return next })
        }
    }, [merge, say])

    // --- the confirmation ---------------------------------------------------------------------------------------
    const review = useCallback((ids: string[], source: PaySource, opener?: Element | null) => {
        sheetOpener.current = opener ?? document.activeElement
        const wanted = [...new Set(ids)]
        setSheet({ ids: wanted, source, phase: "loading", notice: null, error: null })
        void (async () => {
            try {
                const { items } = await previewPayments(wanted)  // fresh, not the cached verdicts
                merge(items)
                const eligible = items.filter(v => v.eligible).map(v => v.invoiceId)
                const ok = eligible.slice(0, MAX_BASKET)
                const left = items.length - eligible.length
                const later = eligible.length - ok.length
                const notes = [
                    left ? `${plural(left, "invoice")} can't be paid from here and ${left === 1 ? "was" : "were"} left out.` : null,
                    later ? `One payment holds at most ${MAX_BASKET} invoices. The other ${later} stay selected for the next one.` : null,
                ].filter(Boolean).join(" ")
                setSheet(prev => prev && {
                    ...prev, ids: ok, phase: "review",
                    error: ok.length ? null : "None of these invoices can be paid from here.",
                    notice: ok.length && notes ? notes : null,
                })
            } catch (e) {
                setSheet(prev => prev && { ...prev, phase: "review", ids: [], error: e instanceof Error ? e.message : "Could not check these invoices." })
            }
        })()
    }, [merge])

    const closeSheet = useCallback(() => setSheet(null), [])

    const queueRef = useRef<QueueItem[] | null>(null)
    useEffect(() => { queueRef.current = queue }, [queue])

    const setStates = useCallback((changes: Record<string, QueueState>) => {
        setQueue(prev => prev && prev.map(i => (changes[i.intentId] ? { ...i, state: changes[i.intentId] } : i)))
    }, [])

    // Opens a payment page again, or the ones a browser blocked. The page opens in a new tab; PayPal itself asks for the payment there.
    const openItem = useCallback(async (intentId: string) => {
        const item = queueRef.current?.find(i => i.intentId === intentId)
        if (!item || (item.state !== "ready" && item.state !== "opened")) return false
        if (Date.parse(item.expiresAt) <= Date.now()) {
            setStates({ [intentId]: "expired" })
            say(`${item.title}: the payment link expired. Review the payment again.`)
            return false
        }
        const [opened] = await openPayPages([item.url])
        if (!opened) { say("Your browser blocked the PayPal tab."); return false }
        if (item.state === "ready") { setStates({ [intentId]: "opened" }); void markPayIntentOpened(intentId).catch(() => undefined) }
        return true
    }, [say, setStates])

    // All the pages open together; a browser that blocks some leaves those "ready" with their own Open button.
    const startQueue = useCallback(async (intents: PayIntent[]) => {
        const items: QueueItem[] = intents.map(i => ({
            intentId: i.intentId, invoiceId: i.invoiceId, title: label(i), amount: i.amount, currency: i.currency,
            url: i.url, expiresAt: i.expiresAt, state: "ready",
        }))
        queueRef.current = items
        setQueue(items)
        const results = await openPayPages(items.map(i => i.url))
        const changes: Record<string, QueueState> = {}
        items.forEach((item, k) => {
            if (results[k]) { changes[item.intentId] = "opened"; void markPayIntentOpened(item.intentId).catch(() => undefined) }
        })
        setStates(changes)
        const opened = results.filter(Boolean).length
        say(opened === items.length
            ? `Opened ${plural(opened, "invoice")} on PayPal. Nothing is paid until you pay on each PayPal page.`
            : `Opened ${opened} of ${items.length} on PayPal. Your browser blocked the rest: press Open on PayPal for them.`)
    }, [say, setStates])

    const confirm = useCallback(async () => {
        const current = sheet
        if (!current || current.phase !== "review" || current.ids.length === 0) return
        const shown = current.ids.map(id => views[id]).filter(Boolean)
        setSheet({ ...current, phase: "paying", error: null })
        try {
            const result = await createPayIntents(current.ids, current.source, sumTotals(shown))
            if (result.ok) {
                void startQueue(result.intents)
                setSelection(prev => { const next = new Set(prev); current.ids.forEach(id => next.delete(id)); return next })
                setSheet(null)
                return
            }
            merge(result.items)
            const ok = result.items.filter(v => v.eligible)
            const gone = result.items.filter(v => !v.eligible)
            const why = gone.length ? ` ${gone.map(v => `${label(v)}: ${v.reasons[0]?.text ?? "cannot be paid"}`).join("; ")}.` : ""
            setSheet({
                ...current, ids: ok.map(v => v.invoiceId), phase: "review",
                notice: `${result.message}${why}${ok.length ? ` The total is now ${totalsText(sumTotals(ok))}.` : ""}`,
                error: ok.length ? null : "None of these invoices can be paid from here any more.",
            })
        } catch (e) {
            setSheet({ ...current, phase: "review", error: e instanceof Error ? e.message : "Something went wrong. Nothing was paid." })
        }
    }, [sheet, views, merge, startQueue])

    // --- payments in progress -----------------------------------------------------------------------------------
    // Dismissing the card cancels pages that never opened, so nothing stays issued behind it.
    const dismissQueue = useCallback(() => {
        (queueRef.current ?? []).filter(i => i.state === "ready").forEach(i => { void cancelPayIntent(i.intentId).catch(() => undefined) })
        setQueue(null)
    }, [])

    // PayPal alone says when an invoice is paid: opened pages are asked about while the panel is open.
    const openedIds = useMemo(() => (queue ?? []).filter(i => i.state === "opened").map(i => i.intentId), [queue])
    useEffect(() => {
        if (openedIds.length === 0) return
        const poll = async () => {
            try {
                const { items } = await fetchPayIntentStatus(openedIds)
                const paid = items.filter(i => i.status === "PAID")
                if (paid.length === 0) return
                const ids = new Set(paid.map(i => i.intentId))
                setQueue(prev => prev && prev.map(i => (ids.has(i.intentId) ? { ...i, state: "paid" } : i)))
                void load(paid.map(i => i.invoiceId))
                say(`PayPal confirmed ${plural(paid.length, "payment")}.`)
            } catch { /* try again at the next tick */ }
        }
        const timer = window.setInterval(() => { void poll() }, POLL_MS)
        const onVisible = () => { if (document.visibilityState === "visible") void poll() }
        document.addEventListener("visibilitychange", onVisible)
        window.addEventListener("focus", onVisible)
        return () => { window.clearInterval(timer); document.removeEventListener("visibilitychange", onVisible); window.removeEventListener("focus", onVisible) }
    }, [openedIds, load, say])

    const inProgress = useMemo(() => new Set((queue ?? []).filter(i => i.state === "ready" || i.state === "opened").map(i => i.invoiceId)), [queue])
    const paid = useMemo(() => new Set((queue ?? []).filter(i => i.state === "paid").map(i => i.invoiceId)), [queue])
    useEffect(() => { inProgressRef.current = inProgress }, [inProgress])

    const value = useMemo<Payments>(() => ({
        views, ensure, selection, toggle, setMany, clearSelection, checking, checkNow, sheet, review, closeSheet, confirm,
        queue, inProgress, paid, openItem, dismissQueue, announce, sheetOpener,
    }), [views, ensure, selection, toggle, setMany, clearSelection, checking, checkNow, sheet, review, closeSheet, confirm,
        queue, inProgress, paid, openItem, dismissQueue, announce])

    return <PaymentsCtx.Provider value={value}>{children}</PaymentsCtx.Provider>
}

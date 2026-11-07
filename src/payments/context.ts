import { createContext, useContext } from "react"
import type { PayView } from "../api/types.js"

export type PaySource = "ui" | "chat"
export type SheetPhase = "loading" | "review" | "paying"
export type Sheet = { ids: string[]; source: PaySource; phase: SheetPhase; notice: string | null; error: string | null }
// ready: the page was issued but its tab did not open (blocked). opened: the tab was opened; not paid until PayPal says so.
export type QueueState = "ready" | "opened" | "paid" | "expired"
export type QueueItem = { intentId: string; invoiceId: string; title: string; amount: string | null; currency: string | null; url: string; expiresAt: string; state: QueueState }

export type Payments = {
    views: Record<string, PayView>
    ensure: (ids: string[]) => void
    selection: ReadonlySet<string>
    toggle: (id: string, on: boolean) => void
    setMany: (ids: string[], on: boolean) => void
    clearSelection: () => void
    checking: ReadonlySet<string>
    checkNow: (id: string) => Promise<void>
    sheet: Sheet | null
    review: (ids: string[], source: PaySource, opener?: Element | null) => void
    closeSheet: () => void
    confirm: () => Promise<void>
    queue: QueueItem[] | null
    // Invoices whose payment page was issued or opened and not yet confirmed: they cannot be started a second time.
    inProgress: ReadonlySet<string>
    paid: ReadonlySet<string>
    openItem: (intentId: string) => Promise<boolean>
    dismissQueue: () => void
    announce: string
    sheetOpener: { current: Element | null }
}

export const PaymentsCtx = createContext<Payments | null>(null)

export function usePayments(): Payments {
    const ctx = useContext(PaymentsCtx)
    if (!ctx) throw new Error("usePayments needs a PaymentsProvider")
    return ctx
}


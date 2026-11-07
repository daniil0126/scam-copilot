import { useCallback, useEffect, useRef, useState } from "react"
import { fetchUnreadCount } from "../../api/client.js"

const POLL_MS = 10_000
const POLL_ERROR_MS = 30_000 // the backend is unreachable: ask less often

// Polls the number of unread alerts for the tab badge. Skips polls while the page is hidden, like useMonitoring.
export function useUnreadCount() {
    const [unread, setUnread] = useState(0)
    const [error, setError] = useState<string | null>(null)
    const load = useRef<() => Promise<void>>(() => Promise.resolve())
    const issued = useRef(0)

    useEffect(() => {
        let cancelled = false
        let timer: ReturnType<typeof setTimeout> | undefined
        const run = async () => {
            let delay = POLL_MS
            if (!document.hidden) {
                try {
                    const ticket = ++issued.current
                    const next = await fetchUnreadCount()
                    // A slower, older answer must not overwrite a newer one: it would show a count from before an alert was read.
                    if (cancelled || ticket !== issued.current) return
                    setUnread(next.unread)
                    setError(null)
                } catch (e) {
                    if (cancelled) return
                    setError(e instanceof Error ? e.message : "Could not load alerts.")
                    delay = POLL_ERROR_MS
                }
            }
            if (!cancelled) timer = setTimeout(() => void run(), delay)
        }
        load.current = async () => {
            clearTimeout(timer)
            await run()
        }
        void run()
        return () => { cancelled = true; clearTimeout(timer) }
    }, [])

    const refresh = useCallback(() => load.current(), [])
    return { unread, error, refresh }
}

export type UnreadCount = ReturnType<typeof useUnreadCount>

import { useCallback, useEffect, useRef, useState } from "react"
import { fetchMonitoring, pauseMonitoring, resumeMonitoring, syncMonitoring } from "../../api/client.js"
import type { MonitoringStatus } from "../../api/types.js"

const POLL_MS = 10_000
const POLL_IDLE_MS = 30_000 // paused or failing: nothing changes on its own, so ask less often

export type MonitoringBusy = "sync" | "toggle" | null

// One poller for the whole panel (header indicator, tab badge, Monitor tab). It skips polls while the page is hidden.
export function useMonitoring() {
    const [status, setStatus] = useState<MonitoringStatus | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [busy, setBusy] = useState<MonitoringBusy>(null)
    const load = useRef<() => Promise<void>>(() => Promise.resolve())

    useEffect(() => {
        let cancelled = false
        let timer: ReturnType<typeof setTimeout> | undefined
        let delay = POLL_MS
        const run = async () => {
            if (!document.hidden) {
                try {
                    const next = await fetchMonitoring()
                    if (cancelled) return
                    setStatus(next)
                    setError(null)
                    delay = next.state === "ACTIVE" ? POLL_MS : POLL_IDLE_MS
                } catch (e) {
                    if (cancelled) return
                    setError(e instanceof Error ? e.message : "Could not load monitoring.")
                    delay = POLL_IDLE_MS
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

    const act = useCallback(async (kind: Exclude<MonitoringBusy, null>, action: () => Promise<unknown>) => {
        setBusy(kind)
        try {
            await action()
        } catch (e) {
            setError(e instanceof Error ? e.message : "The request failed.")
        } finally {
            setBusy(null)
        }
        await load.current()
    }, [])

    return {
        status,
        error,
        busy,
        sync: () => act("sync", syncMonitoring),
        toggle: () => act("toggle", status?.state === "PAUSED" ? resumeMonitoring : pauseMonitoring),
    }
}

export type Monitoring = ReturnType<typeof useMonitoring>

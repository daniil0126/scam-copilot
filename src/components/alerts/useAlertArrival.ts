import { useCallback, useEffect, useRef, useState } from "react"
import { fetchNotifications } from "../../api/client.js"
import type { AppNotification } from "../../api/types.js"

let audio: AudioContext | null = null

// A short two-note chime made with the Web Audio API (no sound file). The browser may keep the audio locked until the
// person has clicked in the panel once; then the alert is silent, which is acceptable: the banner and flash still show.
function chime() {
    try {
        audio ??= new AudioContext()
        if (audio.state === "suspended") void audio.resume()
        const start = audio.currentTime + 0.02
        for (const [i, freq] of [880, 1320].entries()) {
            const osc = audio.createOscillator()
            const gain = audio.createGain()
            const at = start + i * 0.14
            osc.type = "sine"
            osc.frequency.value = freq
            gain.gain.setValueAtTime(0.0001, at)
            gain.gain.exponentialRampToValueAtTime(0.25, at + 0.02)
            gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.35)
            osc.connect(gain).connect(audio.destination)
            osc.start(at)
            osc.stop(at + 0.4)
        }
    } catch { /* no audio available */ }
}

const idOf = (n: AppNotification) => Number(n.id.replace(/^ntf_/, ""))

// Notices a new alert: the newest alert is one this panel has not seen before and is still unread. Judging by the count
// going up would also fire for an alert that was already known (a late poll answer from before it was read, a return after
// a network error). The first reading only sets the baseline. The banner says what arrived.
export function useAlertArrival(unread: number, known: boolean, enabled: boolean) {
    const [arrival, setArrival] = useState<AppNotification | null>(null)
    const [flashKey, setFlashKey] = useState(0)
    const newest = useRef<number | null>(null)  // the highest alert id already accounted for

    useEffect(() => {
        if (!known) return
        let cancelled = false
        fetchNotifications({ limit: 1 })
            .then(page => {
                if (cancelled) return
                const latest = page.items[0]
                const id = latest ? idOf(latest) : 0
                const before = newest.current
                newest.current = Math.max(before ?? 0, id)
                if (before === null || id <= before || latest.read || !enabled) return  // the first reading is not an arrival
                chime()
                setArrival(latest)
                setFlashKey(k => k + 1)
            })
            .catch(() => { /* the next change of the count asks again */ })
        return () => { cancelled = true }
    }, [unread, known, enabled])

    const dismiss = useCallback(() => setArrival(null), [])
    return { arrival, flashKey, dismiss }
}

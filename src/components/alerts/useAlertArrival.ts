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

// Notices a new unread alert: the unread count goes up after the first reading. What arrived is fetched once, so that the
// banner can say what it is about; the count alone would only say that something happened.
export function useAlertArrival(unread: number, known: boolean, enabled: boolean) {
    const [arrival, setArrival] = useState<AppNotification | null>(null)
    const [flashKey, setFlashKey] = useState(0)
    const previous = useRef<number | null>(null)

    useEffect(() => {
        if (!known) return
        const before = previous.current
        previous.current = unread
        if (before === null || unread <= before || !enabled) return  // the first reading is not an arrival
        let cancelled = false
        chime()
        fetchNotifications({ unreadOnly: true, limit: 1 })
            .then(page => { if (!cancelled) { setArrival(page.items[0] ?? null); setFlashKey(k => k + 1) } })
            .catch(() => { if (!cancelled) setFlashKey(k => k + 1) })  // still flash: the count did rise
        return () => { cancelled = true }
    }, [unread, known, enabled])

    const dismiss = useCallback(() => setArrival(null), [])
    return { arrival, flashKey, dismiss }
}

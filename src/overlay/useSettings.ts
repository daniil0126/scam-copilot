import { useCallback, useEffect, useRef, useState } from "react"
import type { UserSettings } from "../types.js"
import { DEFAULT_SETTINGS, loadSettings, normalizeSettings, saveSettings, subscribeSettings } from "../lib/settings.js"

const SAVE_DELAY_MS = 300

export function useSettings() {
    const [settings, setSettings] = useState<UserSettings>(DEFAULT_SETTINGS)
    const latest = useRef(settings)
    const saveTimer = useRef<ReturnType<typeof setTimeout>>(undefined)

    useEffect(() => {
        let alive = true
        loadSettings().then(s => {
            if (!alive) return
            latest.current = s
            setSettings(s)
        })
        const unsubscribe = subscribeSettings(s => {
            latest.current = s
            setSettings(s)
        })
        return () => {
            alive = false
            unsubscribe()
            clearTimeout(saveTimer.current)
        }
    }, [])

    const update = useCallback((patch: Partial<UserSettings>) => {
        const next = normalizeSettings({ ...latest.current, ...patch })
        latest.current = next
        setSettings(next)
        // Debounced so dragging the width slider does not exceed storage.sync write quotas.
        clearTimeout(saveTimer.current)
        saveTimer.current = setTimeout(() => saveSettings(next), SAVE_DELAY_MS)
    }, [])

    return { settings, update }
}

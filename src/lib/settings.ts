import type { UserSettings } from "../types.js"

export const MIN_WIDTH = 280
export const MAX_WIDTH = 560

export const DEFAULT_SETTINGS: UserSettings = {
    theme: "light",
    notifications: true,
    width: 420,
    collapsed: false,
}

const KEY = "scamcopilot-settings"

const hasChromeStorage = () => typeof chrome !== "undefined" && !!chrome.storage?.sync

// Stored data may be missing, stale or edited by hand, so every field is validated.
export function normalizeSettings(raw: Partial<UserSettings> | undefined): UserSettings {
    const d = DEFAULT_SETTINGS
    const width = typeof raw?.width === "number" && Number.isFinite(raw.width) ? raw.width : d.width
    return {
        theme: raw?.theme === "dark" ? "dark" : "light",
        notifications: typeof raw?.notifications === "boolean" ? raw.notifications : d.notifications,
        width: Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, Math.round(width))),
        collapsed: typeof raw?.collapsed === "boolean" ? raw.collapsed : d.collapsed,
    }
}

export async function loadSettings(): Promise<UserSettings> {
    try {
        if (hasChromeStorage()) {
            const data = await chrome.storage.sync.get(KEY)
            return normalizeSettings(data[KEY] as Partial<UserSettings> | undefined)
        }
        const raw = localStorage.getItem(KEY)
        return normalizeSettings(raw ? JSON.parse(raw) : undefined)
    } catch {
        return DEFAULT_SETTINGS
    }
}

export async function saveSettings(settings: UserSettings): Promise<void> {
    try {
        if (hasChromeStorage()) await chrome.storage.sync.set({ [KEY]: settings })
        else localStorage.setItem(KEY, JSON.stringify(settings))
    } catch (error) {
        console.error("Failed to save settings", error)
    }
}

// Keeps several open tabs in sync when settings change in one of them.
export function subscribeSettings(callback: (settings: UserSettings) => void): () => void {
    if (hasChromeStorage()) {
        const listener = (changes: Record<string, chrome.storage.StorageChange>, area: string) => {
            if (area === "sync" && changes[KEY]) callback(normalizeSettings(changes[KEY].newValue as Partial<UserSettings> | undefined))
        }
        chrome.storage.onChanged.addListener(listener)
        return () => chrome.storage.onChanged.removeListener(listener)
    }
    const listener = (e: StorageEvent) => {
        if (e.key === KEY) callback(normalizeSettings(e.newValue ? JSON.parse(e.newValue) : undefined))
    }
    window.addEventListener("storage", listener)
    return () => window.removeEventListener("storage", listener)
}

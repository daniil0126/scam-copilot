import { UserSettings } from "../types.js"

export const DEFAULT_SETTINGS: UserSettings = {
    theme: "light",
    notifications: true,
}

const KEY = "scamcopilot-settings"

const hasChromeStorage = () => typeof chrome !== "undefined" && !!chrome.storage?.sync

export async function loadSettings(): Promise<UserSettings> {
    try {
        if (hasChromeStorage()) {
            const data = await chrome.storage.sync.get(KEY)
            return { ...DEFAULT_SETTINGS, ...(data[KEY] as Partial<UserSettings> | undefined) }
        }
        const raw = localStorage.getItem(KEY)
        return raw ? { ...DEFAULT_SETTINGS, ...JSON.parse(raw) } : DEFAULT_SETTINGS
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

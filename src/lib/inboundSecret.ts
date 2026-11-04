// The secret for POST /inbound/email. Kept in chrome.storage.local (not sync: it must not leave this machine)
// and apart from the other settings, so it never travels with them.
const KEY = "scamcopilot-inbound-secret"

// A release build for the judges can carry the secret of the hosted backend so "Check this email" works out of the box.
const DEFAULT_SECRET = (import.meta.env.VITE_INBOUND_SECRET as string | undefined) || ""

const hasChromeLocal = () => typeof chrome !== "undefined" && !!chrome.storage?.local

export async function loadInboundSecret(): Promise<string> {
    try {
        if (hasChromeLocal()) {
            const data = await chrome.storage.local.get(KEY)
            return typeof data[KEY] === "string" && data[KEY] ? data[KEY] : DEFAULT_SECRET
        }
        return localStorage.getItem(KEY) || DEFAULT_SECRET
    } catch {
        return DEFAULT_SECRET
    }
}

export async function saveInboundSecret(secret: string): Promise<void> {
    try {
        if (hasChromeLocal()) await chrome.storage.local.set({ [KEY]: secret })
        else localStorage.setItem(KEY, secret)
    } catch {
        console.error("Failed to save the inbound secret")
    }
}

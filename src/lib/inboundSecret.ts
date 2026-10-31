// The secret for POST /inbound/email. Kept in chrome.storage.local (not sync: it must not leave this machine)
// and apart from the other settings, so it never travels with them.
const KEY = "scamcopilot-inbound-secret"

const hasChromeLocal = () => typeof chrome !== "undefined" && !!chrome.storage?.local

export async function loadInboundSecret(): Promise<string> {
    try {
        if (hasChromeLocal()) {
            const data = await chrome.storage.local.get(KEY)
            return typeof data[KEY] === "string" ? data[KEY] : ""
        }
        return localStorage.getItem(KEY) ?? ""
    } catch {
        return ""
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

declare global {
    interface Window {
        // Set by the hosted web copy (GET /app/config.js): the server hands its own page the access token.
        __SCAMCOPILOT__?: { token?: string }
    }
}

// True inside the browser extension (side panel), false on the hosted web copy and on the dev page.
export const isExtension = typeof chrome !== "undefined" && !!chrome.runtime?.id

// Where the backend is. The web build sets VITE_API_URL=self (the page and the API share one address); a release build of the
// extension sets the hosted address (and VITE_ACCESS_TOKEN); a plain build talks to localhost.
const configured = import.meta.env.VITE_API_URL as string | undefined
export const API_URL = configured === "self" && typeof window !== "undefined"
    ? window.location.origin
    : configured || "http://localhost:8000"

const BUILT_IN_TOKEN = (import.meta.env.VITE_ACCESS_TOKEN as string | undefined) || ""

// A hosted backend asks for this header on every call (backend/app/access.py); a local one does not, so the header is simply left out.
export const accessHeaders = (): Record<string, string> => {
    const token = (typeof window !== "undefined" ? window.__SCAMCOPILOT__?.token : undefined) || BUILT_IN_TOKEN
    return token ? { "x-access-token": token } : {}
}

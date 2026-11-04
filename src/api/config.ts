// Where the backend is. A release build sets VITE_API_URL (and VITE_ACCESS_TOKEN for a hosted backend); a plain build talks to localhost.
export const API_URL = (import.meta.env.VITE_API_URL as string | undefined) || "http://localhost:8000"

const ACCESS_TOKEN = (import.meta.env.VITE_ACCESS_TOKEN as string | undefined) || ""

// A hosted backend asks for this header on every call (backend/app/access.py); a local one does not, so the header is simply left out.
export const accessHeaders = (): Record<string, string> => (ACCESS_TOKEN ? { "x-access-token": ACCESS_TOKEN } : {})

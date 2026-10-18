export type ExtensionMessage = {
    action: "GET_DOM_STRUCTURE"
}

export type DOMResonse = {
    dom: string
    url: string
}

export type Message = {
    id: number
    role: "user" | "system"
    message: string
}

export type TabId = "check" | "history" | "settings"

export type Theme = "light" | "dark"

export type UserSettings = {
    theme: Theme
    notifications: boolean
}

// Tiny external store for "is the panel open", shared by the content script and the React tree.
export type OpenStore = {
    get: () => boolean
    set: (open: boolean) => void
    toggle: () => void
    subscribe: (callback: () => void) => () => void
}

export function createOpenStore(initial: boolean): OpenStore {
    let open = initial
    const listeners = new Set<() => void>()
    const set = (next: boolean) => {
        if (next === open) return
        open = next
        listeners.forEach(l => l())
    }
    return {
        get: () => open,
        set,
        toggle: () => set(!open),
        subscribe: (callback) => {
            listeners.add(callback)
            return () => { listeners.delete(callback) }
        },
    }
}

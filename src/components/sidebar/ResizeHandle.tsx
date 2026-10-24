import type { KeyboardEvent, PointerEvent } from "react"
import { MAX_WIDTH, MIN_WIDTH } from "../../lib/settings.js"

type Props = {
    width: number
    onResize: (width: number) => void
}

const KEY_STEP = 20

// Drag handle on the inner edge of the panel. The width is clamped by the settings layer.
export default function ResizeHandle({ width, onResize }: Props) {
    const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
        e.currentTarget.setPointerCapture(e.pointerId)
    }

    const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
        if (!e.currentTarget.hasPointerCapture(e.pointerId)) return
        onResize(window.innerWidth - e.clientX)
    }

    const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
        // The panel is docked on the right, so moving its edge left widens it.
        if (e.key === "ArrowLeft") onResize(width + KEY_STEP)
        else if (e.key === "ArrowRight") onResize(width - KEY_STEP)
        else if (e.key === "Home") onResize(MIN_WIDTH)
        else if (e.key === "End") onResize(MAX_WIDTH)
        else return
        e.preventDefault()
    }

    return (
        <div
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize sidebar"
            aria-valuemin={MIN_WIDTH}
            aria-valuemax={MAX_WIDTH}
            aria-valuenow={width}
            tabIndex={0}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onKeyDown={onKeyDown}
            className="absolute top-0 bottom-0 left-0 z-10 w-1.5 cursor-col-resize touch-none bg-transparent transition-colors hover:bg-[var(--primary)]/40 active:bg-[var(--primary)]/60 focus-visible:bg-[var(--primary)]/60 focus-visible:outline-none"
        />
    )
}

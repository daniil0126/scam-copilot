import { useId, useState, type DragEvent } from "react"
import { FileText, Upload, X } from "lucide-react"
import { formatFileSize } from "../../lib/pdf.js"

type Props = {
    file: File | null
    error: string | null
    onSelect: (file: File) => void
    onClear: () => void
    onAnalyse: () => void
}

export default function UploadCard({ file, error, onSelect, onClear, onAnalyse }: Props) {
    const inputId = useId()
    const [dragging, setDragging] = useState(false)

    const onDrop = (e: DragEvent) => {
        e.preventDefault()
        setDragging(false)
        const dropped = e.dataTransfer.files[0]
        if (dropped) onSelect(dropped)
    }

    return (
        <section aria-label="Upload invoice" className="border-b border-[var(--border)] p-4">
            {file ? (
                <div className="flex items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
                    <FileText size={22} className="shrink-0 text-[var(--primary)]" aria-hidden />
                    <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-semibold">{file.name}</span>
                        <span className="block text-xs text-[var(--muted)]">{formatFileSize(file.size)}</span>
                    </span>
                    <button
                        aria-label="Remove file"
                        onClick={onClear}
                        className="rounded-md p-1.5 text-[var(--muted)] hover:bg-[var(--primary-soft)] focus-visible:outline-2 focus-visible:outline-[var(--primary)]"
                    >
                        <X size={16} />
                    </button>
                    <button
                        onClick={onAnalyse}
                        className="rounded-lg bg-[var(--primary)] px-3 py-2 text-sm font-semibold text-white hover:brightness-110 active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"
                    >
                        Analyse
                    </button>
                </div>
            ) : (
                <label
                    htmlFor={inputId}
                    onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
                    onDragLeave={() => setDragging(false)}
                    onDrop={onDrop}
                    className={`flex cursor-pointer flex-col items-center gap-1 rounded-xl border-2 border-dashed px-4 py-5 text-center transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-[var(--primary)] ${dragging ? "border-[var(--primary)] bg-[var(--primary-soft)]" : "border-[var(--border)] bg-[var(--card)] hover:bg-[var(--primary-soft)]"}`}
                >
                    <Upload size={22} className="text-[var(--primary)]" aria-hidden />
                    <span className="text-sm font-semibold">Upload an invoice (PDF)</span>
                    <span className="text-xs text-[var(--muted)]">Drop a file here or click to choose. Up to 10 MB.</span>
                    <input
                        id={inputId}
                        type="file"
                        accept="application/pdf,.pdf"
                        className="sr-only"
                        onChange={(e) => {
                            const chosen = e.target.files?.[0]
                            e.target.value = ""
                            if (chosen) onSelect(chosen)
                        }}
                    />
                </label>
            )}

            {error && <p role="alert" className="mt-2 text-xs font-medium text-[var(--danger)]">{error}</p>}
            <p className="mt-2 text-[11px] leading-snug text-[var(--muted)]">
                The file stays in your browser and is not sent anywhere. Its contents are not analysed yet: the result is sample data.
            </p>
        </section>
    )
}

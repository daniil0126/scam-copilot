export const MAX_PDF_BYTES = 10 * 1024 * 1024

export const formatFileSize = (bytes: number) =>
    bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`

// Returns an error message, or null when the file looks like a usable PDF.
// The extension and MIME type are easy to fake, so the "%PDF-" header is checked too.
export async function validatePdf(file: File): Promise<string | null> {
    const looksLikePdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")
    if (!looksLikePdf) return "Only PDF files are supported."
    if (file.size === 0) return "The file is empty."
    if (file.size > MAX_PDF_BYTES) return `The file is too large (max ${formatFileSize(MAX_PDF_BYTES)}).`
    const header = await file.slice(0, 5).text()
    if (header !== "%PDF-") return "This file is not a valid PDF."
    return null
}

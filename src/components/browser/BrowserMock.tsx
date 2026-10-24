import { ShieldCheck } from "lucide-react"
import InvoicePreview from "./InvoicePreview.js"

export default function BrowserMock({ onToggleSidebar }: { onToggleSidebar: () => void }) {
    return (
        <div className="flex h-screen flex-col bg-slate-100 text-slate-900">
            <div className="flex items-end gap-2 bg-slate-300 px-3 pt-2">
                <div className="mb-2 flex gap-1.5" aria-hidden>
                    <span className="h-3 w-3 rounded-full bg-red-400" />
                    <span className="h-3 w-3 rounded-full bg-amber-400" />
                    <span className="h-3 w-3 rounded-full bg-green-400" />
                </div>
                <div className="ml-3 max-w-[14rem] truncate rounded-t-lg bg-white px-4 py-2 text-xs font-medium">Invoice #45872 - Business</div>
            </div>

            <div className="flex items-center gap-2 border-b border-slate-200 bg-white px-3 py-2">
                <div className="flex-1 truncate rounded-full bg-slate-100 px-4 py-1.5 text-xs text-slate-600">
                    https://business.pay-demo.test/invoice/45872
                </div>
                <button
                    aria-label="Toggle Scam Copilot (simulates clicking the extension icon)"
                    onClick={onToggleSidebar}
                    className="rounded-md p-1.5 text-[#17294b] hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-blue-600"
                >
                    <ShieldCheck size={20} />
                </button>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto bg-slate-50">
                <nav className="flex items-center gap-6 bg-[#0b2a5b] px-6 py-3 text-sm text-white">
                    <span className="text-base font-bold">PayPal-style Business</span>
                    <span className="opacity-80">Summary</span>
                    <span className="opacity-80">Invoices</span>
                    <span className="opacity-80">Reports</span>
                </nav>
                <p className="bg-amber-100 px-6 py-1.5 text-center text-xs text-amber-900">
                    Demo page for UI testing. This is not the real PayPal website.
                </p>
                <div className="p-6"><InvoicePreview /></div>
            </div>
        </div>
    )
}

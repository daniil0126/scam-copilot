import { DEMO_INVOICE, DEMO_LINE_ITEMS } from "../../data/mock.js"
import { formatMoney } from "../../lib/risk.js"

// The mock page uses fixed colours on purpose: the sidebar theme must not restyle the "host page".
export default function InvoicePreview() {
    const { supplier, number, amount, currency, dueDate } = DEMO_INVOICE
    const money = (value: number) => formatMoney(value, currency)
    return (
        <article className="mx-auto w-full max-w-xl rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Invoice {number}</p>
            <h2 className="mt-1 text-xl font-semibold text-slate-900">{supplier.name}</h2>

            <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
                <div>
                    <dt className="text-slate-500">Amount due</dt>
                    <dd className="text-2xl font-bold text-slate-900">{money(amount)}</dd>
                </div>
                <div>
                    <dt className="text-slate-500">Due date</dt>
                    <dd className="font-semibold text-slate-900">
                        {new Date(dueDate + "T00:00:00").toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}
                    </dd>
                </div>
            </dl>

            <table className="mt-6 w-full text-sm">
                <thead>
                    <tr className="border-b border-slate-200 text-left text-slate-500">
                        <th className="py-2 font-medium">Item</th>
                        <th className="py-2 text-right font-medium">Amount</th>
                    </tr>
                </thead>
                <tbody>
                    {DEMO_LINE_ITEMS.map(item => (
                        <tr key={item.label} className="border-b border-slate-100">
                            <td className="py-2 text-slate-700">{item.label}</td>
                            <td className="py-2 text-right text-slate-900">{money(item.amount)}</td>
                        </tr>
                    ))}
                </tbody>
                <tfoot>
                    <tr>
                        <td className="pt-3 font-semibold text-slate-900">Total</td>
                        <td className="pt-3 text-right font-semibold text-slate-900">{money(amount)}</td>
                    </tr>
                </tfoot>
            </table>

            <button
                type="button"
                title="Demo only: does nothing"
                className="mt-6 w-full rounded-full bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-700"
            >
                View and pay
            </button>
        </article>
    )
}

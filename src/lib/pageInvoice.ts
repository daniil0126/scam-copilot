import type { PayPalInvoiceResponse } from "../api/types.js"
import { sendToActiveTab } from "./pageMessage.js"

// Asks the content script of the active tab for the PayPal invoice on it. The text is read only when this is called.
export async function getPageInvoice(): Promise<PayPalInvoiceResponse | null> {
    return (await sendToActiveTab<PayPalInvoiceResponse>({ action: "GET_PAYPAL_INVOICE" })) ?? null
}

import type { PayPalEmailResponse } from "../api/types.js"
import { sendToActiveTab } from "./pageMessage.js"

// Asks the content script of the active tab for the PayPal invoice email on it. The HTML is read only when this is called.
export async function getPageEmail(): Promise<PayPalEmailResponse> {
    return (await sendToActiveTab<PayPalEmailResponse>({ action: "GET_PAYPAL_EMAIL" })) ?? { html: null }
}

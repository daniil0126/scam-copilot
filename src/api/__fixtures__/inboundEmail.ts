// Real answer of POST /inbound/email for the second email of invoice 0068 (backend/tests/fixtures/emails/0068_updated.html), with the amount raised.
// Dev only: nothing in the app imports it, so it is not part of the build. It keeps the type honest against the server output.
import type { InboundEmailResponse } from "../types.js"

export const UPDATED_EMAIL_RESPONSE: InboundEmailResponse = {
    "stored": true,
    "duplicate": false,
    "kind": "updated",
    "template": "RTI003385",
    "invoiceId": "INV2-Z8TH-XHHH-UAP8-TDU2",
    "invoice": {
        "id": "INV2-Z8TH-XHHH-UAP8-TDU2",
        "accountId": null,
        "source": "email",
        "invoiceNumber": "0068",
        "status": null,
        "amount": "175.00",
        "currency": "USD",
        "invoiceDate": null,
        "dueDate": "2026-11-14",
        "senderName": "Test Store",
        "senderLegalName": null,
        "senderEmail": null,
        "senderPhone": null,
        "recipientName": null,
        "recipientEmail": "sb-fuybk48955257@business.example.com",
        "paymentTerms": null,
        "items": [
            {
                "name": "Test item",
                "description": null,
                "quantity": "1",
                "unitAmount": "175.00"
            }
        ],
        "paymentLinks": [
            "https://www.sandbox.paypal.com/invoice/payerView/details/INV2-Z8TH-XHHH-UAP8-TDU2"
        ],
        "note": null,
        "createdAt": null,
        "updatedAt": null,
        "contentHash": "783130066087707cc83e11ecd52352a7ed6e547d20ec001166f3921a0f06ea63"
    },
    "links": [
        {
            "url": "https://www.sandbox.paypal.com/invoice/payerView/details/INV2-Z8TH-XHHH-UAP8-TDU2",
            "text": "View and Pay Invoice",
            "host": "www.sandbox.paypal.com",
            "isPaypal": true,
            "textMismatch": false
        },
        {
            "url": "https://www.sandbox.paypal.com/invoice/payerView/details/INV2-Z8TH-XHHH-UAP8-TDU2",
            "text": "report abuse to PayPal",
            "host": "www.sandbox.paypal.com",
            "isPaypal": true,
            "textMismatch": false
        }
    ],
    "check": {
        "id": "9993f07e-85a3-48be-91ff-a4a77dddc1f3",
        "invoice": {
            "number": "0068",
            "supplier": {
                "name": "Test Store",
                "email": "",
                "phone": ""
            },
            "note": "",
            "amount": 175.0,
            "currency": "USD",
            "dueDate": "2026-11-14",
            "status": ""
        },
        "checkedAt": "2026-10-31T13:36:44Z",
        "level": "medium",
        "score": 40,
        "findings": [
            {
                "id": "supplier",
                "label": "New supplier",
                "severity": "medium"
            },
            {
                "id": "email-amount",
                "label": "Amount raised after sending",
                "severity": "medium"
            }
        ],
        "comparison": [
            {
                "field": "Amount (earlier email)",
                "current": "175.00 USD",
                "previous": "100.00 USD",
                "differs": true
            },
            {
                "field": "Due date (earlier email)",
                "current": "2026-11-14",
                "previous": "2026-11-14",
                "differs": false
            }
        ],
        "recommendation": "Some details look unusual. Verify them with the supplier before paying.",
        "evidence": [
            "This supplier has no earlier checks in your history.",
            "The total went from 100.00 to 175.00 (+75%) after the invoice was sent."
        ]
    }
}

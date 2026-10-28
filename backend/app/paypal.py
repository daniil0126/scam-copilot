import os
import time
from datetime import date, timedelta

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

load_dotenv()

PAYPAL_MODE = os.getenv("PAYPAL_MODE", "sandbox")
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
BASE_URL = "https://api-m.paypal.com" if PAYPAL_MODE == "live" else "https://api-m.sandbox.paypal.com"

router = APIRouter(prefix="/paypal", tags=["paypal"])

_token: dict = {"value": None, "expires_at": 0.0}


async def get_access_token(client: httpx.AsyncClient) -> str:
    if _token["value"] and time.time() < _token["expires_at"] - 60:
        return _token["value"]
    if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
        raise HTTPException(500, "PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET are not set")
    res = await client.post(
        f"{BASE_URL}/v1/oauth2/token",
        auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET),
        data={"grant_type": "client_credentials"},
    )
    if res.status_code != 200:
        raise HTTPException(502, f"PayPal auth failed: {res.text}")
    body = res.json()
    _token["value"] = body["access_token"]
    _token["expires_at"] = time.time() + body["expires_in"]
    return _token["value"]


async def paypal_request(method: str, path: str, json: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        token = await get_access_token(client)
        res = await client.request(
            method, f"{BASE_URL}{path}", json=json, headers={"Authorization": f"Bearer {token}"}
        )
    if res.status_code == 404:
        raise HTTPException(404, "Invoice not found in PayPal")
    if res.status_code >= 400:
        raise HTTPException(502, f"PayPal error {res.status_code}: {res.text}")
    return res.json() if res.content else {}


def to_invoice(data: dict) -> dict:
    """Maps a PayPal invoice to the frontend `Invoice` shape (src/api/types.ts)."""
    detail = data.get("detail", {})
    invoicer = data.get("invoicer", {})
    amount = data.get("amount", {})
    name = invoicer.get("business_name") or " ".join(
        filter(None, [invoicer.get("name", {}).get("given_name"), invoicer.get("name", {}).get("surname")])
    )
    phones = invoicer.get("phones", [])
    note = "\n".join(filter(None, [detail.get("note"), detail.get("memo"), detail.get("terms_and_conditions")]))
    return {
        "number": detail.get("invoice_number", ""),
        "supplier": {
            "name": name,
            "email": invoicer.get("email_address", ""),
            "phone": " ".join(filter(None, [phones[0].get("country_code"), phones[0].get("national_number")])) if phones else "",
        },
        "note": note,
        "amount": float(amount.get("value", 0)),
        "currency": amount.get("currency_code", detail.get("currency_code", "")),
        "dueDate": detail.get("payment_term", {}).get("due_date", ""),
        "status": data.get("status", ""),
    }


@router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: str):
    """Fetches an invoice from PayPal Invoicing API v2."""
    data = await paypal_request("GET", f"/v2/invoicing/invoices/{invoice_id}")
    return to_invoice(data)


class SeedInvoice(BaseModel):
    recipient_email: str
    amount: str = "100.00"
    currency: str = "USD"
    supplier_name: str = "Test Supplier Ltd."
    supplier_email: str | None = None
    supplier_phone: str | None = None
    note: str = "ScamCopilot sandbox test"
    due_in_days: int = 14


@router.post("/sandbox/invoices")
async def create_sandbox_invoice(body: SeedInvoice):
    """Creates a draft invoice, only available in sandbox mode. Handy for testing."""
    if PAYPAL_MODE != "sandbox":
        raise HTTPException(403, "Only available in sandbox mode")
    payload = {
        "detail": {
            "currency_code": body.currency,
            "note": body.note,
            "payment_term": {"due_date": (date.today() + timedelta(days=body.due_in_days)).isoformat()},
        },
        "invoicer": {
            "business_name": body.supplier_name,
            **({"email_address": body.supplier_email} if body.supplier_email else {}),
            **({"phones": [{"country_code": "001", "national_number": body.supplier_phone, "phone_type": "MOBILE"}]}
               if body.supplier_phone else {}),
        },
        "primary_recipients": [{"billing_info": {"email_address": body.recipient_email}}],
        "items": [
            {
                "name": "Test item",
                "quantity": "1",
                "unit_amount": {"currency_code": body.currency, "value": body.amount},
            }
        ],
    }
    created = await paypal_request("POST", "/v2/invoicing/invoices", json=payload)
    invoice_id = created["href"].rstrip("/").split("/")[-1]
    return {"id": invoice_id, **to_invoice(await paypal_request("GET", f"/v2/invoicing/invoices/{invoice_id}"))}


@router.post("/sandbox/invoices/{invoice_id}/send")
async def send_sandbox_invoice(invoice_id: str):
    """Sends a draft invoice (sandbox only), so it gets the invoicer details and a due date."""
    if PAYPAL_MODE != "sandbox":
        raise HTTPException(403, "Only available in sandbox mode")
    await paypal_request("POST", f"/v2/invoicing/invoices/{invoice_id}/send", json={"send_to_recipient": True})
    return {"id": invoice_id, **to_invoice(await paypal_request("GET", f"/v2/invoicing/invoices/{invoice_id}"))}

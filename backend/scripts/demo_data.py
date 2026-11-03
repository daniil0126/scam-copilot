"""Demo data for the video, through the running backend (sandbox only).

    .venv/bin/python scripts/demo_data.py background   # 6 ordinary invoices, created and sent, for History and Monitor
    .venv/bin/python scripts/demo_data.py hook         # scene 1-2: the fake renewal with a phone number
    .venv/bin/python scripts/demo_data.py changed      # scene 3: sends an invoice, `changed --edit <id>` then edits its note
    .venv/bin/python scripts/demo_data.py live         # scene 4: one new invoice, run it while the Monitor tab is open (retake: --name "Other Name")

Each command prints the invoice id and the payer-page link. No real brand names.
"""
import argparse
import asyncio
import os
import sys

import httpx

API = os.getenv("API", "http://localhost:8000")
RECIPIENT = os.getenv("SANDBOX_RECIPIENT", "sb-kckt753313725@personal.example.com")

BACKGROUND = [
    dict(supplier_name="Blue Harbor Plumbing", amount="180.00", note="Kitchen tap repair, October"),
    dict(supplier_name="Sunrise Bakery", amount="52.30", note="Office breakfast order"),
    dict(supplier_name="Northwind Office Supplies", amount="64.90", note="Paper and toner"),
    dict(supplier_name="Blue Harbor Plumbing", amount="165.00", note="Boiler check"),
    dict(supplier_name="City Gym Membership", amount="39.99", note="Monthly membership"),
    dict(supplier_name="Greenfield Catering", amount="420.00", note="Team lunch, 12 people"),
]
HOOK = dict(supplier_name="Premium Antivirus Renewal", amount="499.00", due_in_days=2,
            note="Your subscription has been renewed and charged. If unauthorized, call 1-888-555-0142 to cancel and get a refund.")
CHANGED = dict(supplier_name="Redwood Legal Consulting", amount="890.00", note="Consulting, October hours.")
CHANGED_NOTE = "Consulting, October hours. Our bank details changed: confirm by phone +1 (888) 555-0177 before paying."
LIVE = dict(supplier_name="Secure Shield Renewals", amount="499.99", due_in_days=2,
            note="Your subscription was auto-renewed and charged 499.99 USD. To cancel and get a refund call now +1 (888) 555-0142.")


def link(invoice_id: str) -> str:
    return "https://www.sandbox.paypal.com/invoice/p/#" + invoice_id.removeprefix("INV2-").replace("-", "")


def create_and_send(c: httpx.Client, fields: dict) -> str:
    r = c.post(f"{API}/paypal/sandbox/invoices", json={"recipient_email": RECIPIENT, **fields})
    r.raise_for_status()
    invoice_id = r.json()["id"]
    c.post(f"{API}/paypal/sandbox/invoices/{invoice_id}/send").raise_for_status()
    print(f"{fields['supplier_name']:28} {fields['amount']:>8}  {invoice_id}\n    {link(invoice_id)}")
    return invoice_id


async def edit_note(invoice_id: str, note: str) -> None:
    """Changes the note of a sent invoice and lets PayPal send the update email to the payer."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.paypal import PAYPAL_MODE, paypal_request
    assert PAYPAL_MODE == "sandbox"
    path = f"/v2/invoicing/invoices/{invoice_id}"
    invoice = await paypal_request("GET", path)
    invoice["detail"]["note"] = note
    await paypal_request("PUT", f"{path}?send_to_recipient=true&send_to_invoicer=false", json=invoice)
    print(f"note changed on {invoice_id}; the update email is in Developer Dashboard -> Sandbox notifications")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("what", choices=["background", "hook", "changed", "live"])
    p.add_argument("--name", help="with `live`: another supplier name, for a retake (the earlier one is already in History)")
    p.add_argument("--edit", metavar="INVOICE_ID", help="with `changed`: edit the note of this invoice instead of creating one")
    a = p.parse_args()
    if a.what == "changed" and a.edit:
        asyncio.run(edit_note(a.edit, CHANGED_NOTE))
        return
    with httpx.Client(timeout=60) as c:
        if a.what == "background":
            import time
            for f in BACKGROUND:
                create_and_send(c, f)
                time.sleep(1)
        else:
            fields = {"hook": HOOK, "changed": CHANGED, "live": LIVE}[a.what]
            create_and_send(c, {**fields, "supplier_name": a.name} if a.name else fields)


if __name__ == "__main__":
    main()

"""Creates sandbox invoices for the demo scenarios and checks them in order against a throwaway database.

    .venv/bin/python scripts/scenarios.py            # create + verify expected risk levels
    .venv/bin/python scripts/scenarios.py --links    # only create invoices and print links for manual testing in the browser

Order matters: later scenarios compare with earlier ones from the same supplier.
"""
import asyncio
import os
import sys
import tempfile

RECIPIENT = os.getenv("SANDBOX_RECIPIENT", "sb-kckt753313725@personal.example.com")
ACME = "billing@acme-supplies.example.com"

# (title, seed fields, expected level)
SCENARIOS = [
    ("1. First invoice from a new supplier", dict(supplier_name="Acme Supplies Ltd.", supplier_email=ACME, amount="100.00"), "low"),
    ("2. Same supplier, amount +10%", dict(supplier_name="Acme Supplies Ltd.", supplier_email=ACME, amount="110.00"), "low"),
    ("3. Same supplier, amount x4.5", dict(supplier_name="Acme Supplies Ltd.", supplier_email=ACME, amount="500.00"), "medium"),
    ("4. Same supplier, payment email swapped", dict(supplier_name="Acme Supplies Ltd.", supplier_email="pay@acme-supp1ies.example.com", amount="100.00"), "high"),
    ("5. Same PayPal email, different name", dict(supplier_name="Totally New Name", supplier_email=ACME, amount="100.00"), "medium"),
    ("6. Fake Norton invoice with phone number", dict(supplier_name="Norton Security Renewal", supplier_email="qx7731@mail-pay.example.com", amount="499.00",
        supplier_phone="8885550142", note="Your subscription has been renewed and charged. If unauthorized, call 1-888-555-0142 to cancel and get a refund."), "high"),
    ("7. Ordinary small invoice, new supplier", dict(supplier_name="Local Print Shop", supplier_email="orders@localprint.example.com", amount="60.00", note="Business cards, 500 pcs"), "low"),
]


async def main(links_only: bool):
    if not links_only:
        os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/scenarios.db"
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.paypal import paypal_request

    failed = 0
    for title, fields, expected in SCENARIOS:
        created = await paypal_request("POST", "/v2/invoicing/invoices", json=_payload(fields))
        invoice_id = created["href"].rstrip("/").split("/")[-1]
        # Drafts are enough: PayPal refuses to send invoices whose invoicer email is not a real sandbox account.
        if links_only:
            raw = await paypal_request("GET", f"/v2/invoicing/invoices/{invoice_id}")
            print(f"{title}\n   expected: {expected}\n   {invoice_id}\n   {raw['detail']['metadata']['invoicer_view_url']}")
            continue
        from app.checks import CheckRequest, create_check
        from app.db import Base, SessionLocal, engine
        import app.models  # noqa: F401
        Base.metadata.create_all(engine)
        with SessionLocal() as db:
            r = await create_check(CheckRequest(invoice_id=invoice_id), db)
        ok = r["level"] == expected
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {title}: {r['level']} ({r['score']}), expected {expected}")
        for f in r["findings"]:
            print(f"        [{f['severity']}] {f['label']}")
    if failed:
        sys.exit(f"{failed} scenario(s) failed")


def _payload(f):
    from datetime import date, timedelta
    return {
        "detail": {"currency_code": "USD", "note": f.get("note", "Scenario"),
                   "payment_term": {"due_date": (date.today() + timedelta(days=14)).isoformat()}},
        "invoicer": {"business_name": f["supplier_name"], "email_address": f["supplier_email"],
                     **({"phones": [{"country_code": "001", "national_number": f["supplier_phone"], "phone_type": "MOBILE"}]} if f.get("supplier_phone") else {})},
        "primary_recipients": [{"billing_info": {"email_address": RECIPIENT}}],
        "items": [{"name": "Test item", "quantity": "1", "unit_amount": {"currency_code": "USD", "value": f["amount"]}}],
    }


if __name__ == "__main__":
    asyncio.run(main("--links" in sys.argv))

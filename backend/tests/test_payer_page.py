import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.normalize import normalize_payer_page
from app.payer_page import invoice_id_from_url, is_payer_page, parse_payer_page

DIR = Path(__file__).parent / "fixtures/payer_pages"
load = lambda name: json.loads((DIR / f"{name}.json").read_text())


def test_page_without_dba_has_the_issuer_email_and_address():
    f = load("0055_plain")
    p = parse_payer_page(f["text"])
    assert p["number"] == "0055" and p["displayName"] == "Test Store" and p["legalName"] is None
    assert p["senderEmail"] == "sb-rgubl53282606@business.example.com"
    assert p["address"] == "Free Trade Zone, Astana, 010000, KAZAKHSTAN"
    assert p["amount"] == Decimal("299.00") and p["currency"] == "USD"
    assert p["issued"] == date(2026, 10, 30) and p["dueText"] == "Due today" and p["dueDate"] is None
    assert p["recipientEmail"] == "sb-kckt753313725@personal.example.com"
    assert p["note"] is None and p["items"] == [{"name": "Chicken Nuggets", "description": None, "quantity": None, "unitAmount": None}]


@pytest.mark.parametrize("name,amount", [("0006_dba", "110.00"), ("0007_dba", "500.00")])
def test_page_with_a_doing_business_as_name(name, amount):
    p = parse_payer_page(load(name)["text"])
    assert p["displayName"] == "Acme Supplies Ltd." and p["legalName"] == "Test Store"
    assert p["senderEmail"] is None  # the page does not show it for these invoices
    assert p["amount"] == Decimal(amount) and p["dueDate"] == date(2026, 11, 11)
    assert p["note"] == "ScamCopilot sandbox test"
    assert p["items"] == [{"name": "Test item", "description": None, "quantity": "1", "unitAmount": amount}]


def test_detects_payer_pages_only():
    f = load("0055_plain")
    assert is_payer_page(f["url"], f["text"])
    assert not is_payer_page("https://evil.example.com/invoice/p/#5BEXVJZWMSZMJRVQ", f["text"])
    assert not is_payer_page("https://www.sandbox.paypal.com/invoice/details/INV2-5BEX-VJZW-MSZM-JRVQ", f["text"])
    assert not is_payer_page(f["url"], "Draft invoice\nSend")  # the issuer's own page


def test_unknown_text_gives_empty_fields_not_an_error():
    p = parse_payer_page("hello world")
    assert all(v is None for v in p.values())


def test_ambiguous_due_date_is_not_guessed():
    text = "Invoice #1\n\nAcme\n\n10.00 US$\n\nDue by 03/04/2026\n\nAmount due\nReport invoice"
    assert parse_payer_page(text)["dueDate"] is None
    assert parse_payer_page(text.replace("03/04", "25/04"))["dueDate"] == date(2026, 4, 25)
    assert parse_payer_page(text.replace("03/04", "04/25"))["dueDate"] == date(2026, 4, 25)


def test_unknown_currency_symbol_is_not_guessed():
    p = parse_payer_page("Invoice #1\n\nAcme\n\n10.00 €\n")
    assert p["amount"] == Decimal("10.00") and p["currency"] is None


def test_id_comes_from_the_url_hash_in_api_form():
    assert invoice_id_from_url("https://www.sandbox.paypal.com/invoice/p/#5BEXVJZWMSZMJRVQ") == "INV2-5BEX-VJZW-MSZM-JRVQ"
    assert invoice_id_from_url("https://www.sandbox.paypal.com/invoice/p/") is None


def test_normalized_invoice():
    f = load("0006_dba")
    inv = normalize_payer_page(f["url"], f["text"])
    assert inv.source == "payer_page" and inv.accountId is None and inv.id == "INV2-HHT8-PAHY-B2ZN-N25L"
    assert inv.senderName == "Acme Supplies Ltd." and inv.senderLegalName == "Test Store" and inv.senderEmail is None
    assert inv.model_dump(mode="json")["amount"] == "110.00" and inv.paymentLinks is None
    assert inv.contentHash == normalize_payer_page(f["url"], f["text"]).contentHash


def test_page_and_api_agree_on_the_same_invoice():
    """#0055 exists as a real API response and as a real page; the shared fields must match."""
    from app.normalize import normalize_paypal
    api = normalize_paypal(json.loads((Path(__file__).parent / "fixtures/paypal/invoice_detail_sandbox.json").read_text()))
    f = load("0055_plain")
    page = normalize_payer_page(f["url"], f["text"])
    for field in ("id", "invoiceNumber", "amount", "currency", "invoiceDate", "senderName", "senderEmail", "recipientEmail"):
        assert getattr(page, field) == getattr(api, field), field
    assert api.senderPhone and page.senderPhone is None  # the page does not show the phone


def test_link_in_the_page_note_reaches_payment_links():
    f = load("0006_dba")
    text = f["text"].replace("ScamCopilot sandbox test", "Cancel at https://norton-help.example.net/cancel.")
    inv = normalize_payer_page(f["url"], text)
    assert inv.note == "Cancel at https://norton-help.example.net/cancel." and inv.paymentLinks == ["https://norton-help.example.net/cancel"]

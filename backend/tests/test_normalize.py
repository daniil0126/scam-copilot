import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.normalize import normalize_paypal

RAW = json.loads((Path(__file__).parent / "fixtures/paypal/invoice_detail_sandbox.json").read_text())


def test_real_sandbox_response_is_mapped():
    inv = normalize_paypal(RAW)
    assert inv.id == RAW["id"] and inv.source == "paypal_api" and inv.accountId is None
    assert inv.amount == Decimal(RAW["amount"]["value"]) and inv.currency == RAW["amount"]["currency_code"]
    assert inv.invoiceDate == date.fromisoformat(RAW["detail"]["invoice_date"])
    assert inv.dueDate == date.fromisoformat(RAW["detail"]["payment_term"]["due_date"])
    assert inv.senderName == "Test Store" and inv.senderEmail == RAW["invoicer"]["email_address"].lower()
    assert inv.senderPhone == f'{RAW["invoicer"]["phones"][0]["country_code"]} {RAW["invoicer"]["phones"][0]["national_number"]}'
    assert inv.recipientEmail == RAW["primary_recipients"][0]["billing_info"]["email_address"].lower()
    assert inv.items and inv.items[0].name == RAW["items"][0]["name"] and inv.items[0].description is None
    assert inv.paymentLinks == [RAW["detail"]["metadata"]["recipient_view_url"]]
    assert inv.updatedAt is not None and inv.createdAt is not None


def test_missing_fields_stay_none_not_guessed():
    inv = normalize_paypal({"id": "INV2-X"})
    assert inv.id == "INV2-X"
    assert all(getattr(inv, f) is None for f in (
        "amount", "currency", "invoiceDate", "dueDate", "senderName", "senderEmail", "recipientName", "items", "paymentLinks", "note"))


def test_api_operation_links_are_not_payment_links():
    inv = normalize_paypal({"id": "INV2-X", "links": [{"href": "https://api.sandbox.paypal.com/x", "rel": "cancel", "method": "POST"}]})
    assert inv.paymentLinks is None


def test_hash_ignores_timestamps_but_not_content():
    base = normalize_paypal(RAW)
    touched = json.loads(json.dumps(RAW))
    touched["detail"]["metadata"]["last_update_time"] = "2030-01-01T00:00:00Z"
    assert normalize_paypal(touched).contentHash == base.contentHash
    touched["amount"]["value"] = "999999.00"
    assert normalize_paypal(touched).contentHash != base.contentHash


def test_amount_serializes_as_string():
    assert normalize_paypal({"id": "A", "amount": {"value": "123.45", "currency_code": "usd"}}).model_dump(mode="json")["amount"] == "123.45"


def test_links_are_extracted_as_written_and_deduplicated():
    from app.normalize import extract_links
    text = "Pay at https://paypa1-secure.example.com/pay?id=1, or www.Evil.example.net. Again: https://paypa1-secure.example.com/pay?id=1"
    assert extract_links(text, None, "see (http://203.0.113.7/x) now") == [
        "https://paypa1-secure.example.com/pay?id=1", "www.Evil.example.net", "http://203.0.113.7/x"]
    assert extract_links("call 1-888-555-0142 or mail a@b.example.com", "") == []
    assert extract_links("https://xn--pypal-4ve.example.com/") == ["https://xn--pypal-4ve.example.com/"]


def test_links_in_the_note_reach_payment_links_next_to_paypals_own_page():
    raw = json.loads(json.dumps(RAW))
    raw["detail"]["note"] = "Renewal. Cancel at https://norton-help.example.net/cancel"
    inv = normalize_paypal(raw)
    assert inv.paymentLinks == [RAW["detail"]["metadata"]["recipient_view_url"], "https://norton-help.example.net/cancel"]

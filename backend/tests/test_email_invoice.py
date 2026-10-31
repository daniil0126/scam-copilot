from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.email_invoice import MAX_HTML, link_host, link_is_paypal, parse_invoice_email
from app.normalize import normalize_email

DIR = Path(__file__).parent / "fixtures/emails"
load = lambda name: (DIR / f"{name}.html").read_text()
INVOICE = "INV2-Z8TH-XHHH-UAP8-TDU2"


def test_new_invoice_email_is_read_in_full():
    m = parse_invoice_email(load("0068_new"))
    assert m["kind"] == "new" and m["template"] == "RTI003384"
    assert m["merchant"] == "Test Store" and m["number"] == "0068" and m["invoiceId"] == INVOICE
    assert m["amount"] == Decimal("100.00") and m["currency"] == "USD" and m["dueDate"] == date(2026, 11, 14)
    assert m["note"] == "A to B v0"
    assert m["items"] == [{"name": "Test item", "description": None, "quantity": "1", "unitAmount": "100.00"}]
    assert m["recipientEmail"] == "sb-fuybk48955257@business.example.com" and m["recipientName"] is None
    assert m["primaryLink"]["isPaypal"] and m["primaryLink"]["host"] == "www.sandbox.paypal.com"


def test_update_email_has_the_new_amount_and_no_note():
    m = parse_invoice_email(load("0068_updated"))
    assert m["kind"] == "updated" and m["template"] == "RTI003385" and m["invoiceId"] == INVOICE
    assert m["amount"] == Decimal("175.00") and m["items"][0]["unitAmount"] == "175.00"
    assert m["note"] is None  # PayPal leaves the note out of update emails: unknown, not removed


def test_the_hidden_pre_header_is_not_read_as_content():
    m = parse_invoice_email(load("0068_new"))
    assert m["note"] == "A to B v0" and all("here are your" not in (i["name"] or "") for i in m["items"])


def test_the_issuer_confirmation_is_not_taken_for_a_payer_notice():
    m = parse_invoice_email(load("issuer_copy"))
    assert m["kind"] == "issuer_copy"
    assert m["amount"] is None and m["invoiceId"] is None and m["items"] is None


def test_garbage_gives_unknown_and_empty_fields():
    for html in ["", "plain text, no markup", "<div><a href>broken", "<<<>>>&&&"]:
        m = parse_invoice_email(html)
        assert m["kind"] == "unknown" and m["amount"] is None and m["invoiceId"] is None and m["items"] is None


def test_oversized_email_is_refused():
    with pytest.raises(ValueError):
        parse_invoice_email("a" * (MAX_HTML + 1))


@pytest.mark.parametrize("url,host", [
    ("https://www.paypal.com/invoice/payerView/details/INV2-AAAA-BBBB-CCCC-DDDD", "www.paypal.com"),
    ("https://WWW.SANDBOX.PAYPAL.COM./x", "www.sandbox.paypal.com"),
    ("https://paypal.com", "paypal.com"),
    ("http://www.paypal.com/x", None),  # not https
    ("javascript:alert(1)", None),
    ("//www.paypal.com/x", None),
    ("https://www.paypal.com@evil.example/x", None),  # user-info trick
    ("https://evil.example\\@www.paypal.com/x", None),  # a browser reads the backslash as a slash
    ("https://www.paypal.com\t.evil.example/", None),
    ("", None),
])
def test_link_host_refuses_tricks(url, host):
    assert link_host(url) == host


@pytest.mark.parametrize("url", [
    "https://www.paypal.com.evil.example/invoice",
    "https://evil.example/?next=https://www.paypal.com/invoice",
    "https://paypal-invoice.example/pay",
    "https://www.paypa1.com/invoice",
    "https://xn--pypal-4ve.com/invoice",  # punycode lookalike
    "https://notpaypal.com/invoice",
    "https://www.paypal.com@evil.example/invoice",
])
def test_lookalike_hosts_are_not_paypal(url):
    assert not link_is_paypal(url)


def test_spoofed_button_is_flagged_and_its_invoice_id_is_not_trusted():
    html = load("0068_new").replace("https://www.sandbox.paypal.com/invoice/payerView/details/" + INVOICE + "?v=1",
                                    "https://www.paypal.com.secure-pay.example/invoice/payerView/details/" + INVOICE + "?v=1", 1)
    m = parse_invoice_email(html)
    assert m["primaryLink"]["isPaypal"] is False
    assert m["invoiceId"] is None
    assert m["kind"] == "new"  # the look of the email is not evidence either way: the link decides


def test_link_text_that_names_another_address_is_flagged():
    html = '<p>Hello, a@b.example</p><a href="https://evil.example/x">www.paypal.com/invoice</a><a href="https://www.paypal.com/x">www.paypal.com/x</a>'
    links = {l["host"]: l for l in parse_invoice_email(html)["links"]}
    assert links["evil.example"]["textMismatch"] is True
    assert links["www.paypal.com"]["textMismatch"] is False


def test_a_look_alike_email_without_paypals_structure_is_still_judged_by_its_links():
    html = "<p>Invoice due now, pay at once</p><a href='https://paypal-billing.example/pay'>View Invoice</a>"
    m = parse_invoice_email(html)
    assert m["kind"] == "unknown" and m["primaryLink"]["isPaypal"] is False and m["invoiceId"] is None


def test_other_date_formats_stay_unknown_instead_of_guessed():
    html = load("0068_new").replace("Due on Nov 14, 2026", "Due on 14/11/2026")
    assert parse_invoice_email(html)["dueDate"] is None


def test_normalize_email_gives_the_common_invoice():
    inv = normalize_email(load("0068_new"))
    assert inv.source == "email" and inv.id == INVOICE and inv.invoiceNumber == "0068"
    assert inv.amount == Decimal("100.00") and inv.dueDate == date(2026, 11, 14) and inv.senderName == "Test Store"
    assert inv.senderEmail is None and inv.senderPhone is None  # not in these emails
    assert inv.note == "A to B v0" and inv.paymentLinks and inv.paymentLinks[0].startswith("https://www.sandbox.paypal.com/")


def test_normalize_email_hash_follows_content():
    new, again, updated = (normalize_email(load(n)) for n in ("0068_new", "0068_new", "0068_updated"))
    assert new.contentHash == again.contentHash
    assert new.contentHash != updated.contentHash and updated.note is None


def _link_mismatch(shown: str, href: str) -> bool:
    html = f'<a href="{href}">View and Pay Invoice</a><a href="{href}">{shown}</a>'
    return parse_invoice_email(html)["links"][1]["textMismatch"]


@pytest.mark.parametrize("shown,href", [
    ("PayPal.com", "https://www.paypal.com/us/home"),  # a footer link of a real page: the www host is the same site
    ("paypal.com", "https://www.sandbox.paypal.com/x"),
    ("www.paypal.com", "https://paypal.com/x"),
])
def test_a_link_to_the_site_it_names_or_its_subdomain_is_not_a_mismatch(shown, href):
    assert not _link_mismatch(shown, href)


@pytest.mark.parametrize("shown,href", [
    ("paypal.com", "https://paypal.com.evil.example/x"),
    ("paypal.com", "https://notpaypal.com/x"),
    ("www.paypal.com", "https://evil.example/paypal.com"),
    ("sandbox.paypal.com", "https://www.paypal.com/x"),  # the parent opened, not the named subdomain
])
def test_a_link_that_opens_another_site_is_a_mismatch(shown, href):
    assert _link_mismatch(shown, href)

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.db import SessionLocal
from app.email_invoice import MAX_HTML
from app.main import app
from app.models import Check, InvoiceEmail

client = TestClient(app)
DIR = Path(__file__).parent / "fixtures/emails"
mail = lambda name: (DIR / f"{name}.html").read_text()
HEAD = {"X-Inbound-Secret": "s3cret", "Content-Type": "text/html"}


@pytest.fixture(autouse=True)
def secret(monkeypatch):
    monkeypatch.setenv("INBOUND_EMAIL_SECRET", "s3cret")
    with SessionLocal() as db:
        db.execute(delete(InvoiceEmail))
        db.execute(delete(Check))
        db.commit()


def post(html, headers=HEAD):
    return client.post("/inbound/email", content=html.encode(), headers=headers)


def rows():
    with SessionLocal() as db:
        return db.scalars(select(InvoiceEmail).order_by(InvoiceEmail.row_id)).all()


def test_off_without_a_configured_secret(monkeypatch):
    monkeypatch.delenv("INBOUND_EMAIL_SECRET")
    assert post(mail("0068_new")).status_code == 503 and not rows()


def test_the_extension_needs_no_secret_even_when_none_is_configured(monkeypatch):
    monkeypatch.delenv("INBOUND_EMAIL_SECRET")
    monkeypatch.setenv("PROJECT_ID", "extid")
    r = post(mail("0068_new"), {"Content-Type": "text/html", "Origin": "chrome-extension://extid"})
    assert r.status_code == 200 and rows()


def test_another_origin_is_not_the_extension(monkeypatch):
    monkeypatch.setenv("PROJECT_ID", "extid")
    for origin in ("https://evil.example", "chrome-extension://other"):
        r = post(mail("0068_new"), {"Content-Type": "text/html", "Origin": origin})
        assert r.status_code == 401
    assert not rows()


@pytest.mark.parametrize("headers", [{"Content-Type": "text/html"}, {**HEAD, "X-Inbound-Secret": "wrong"}, {**HEAD, "X-Inbound-Secret": ""}])
def test_wrong_or_missing_secret_stores_nothing(headers):
    assert post(mail("0068_new"), headers).status_code == 401 and not rows()


def test_a_new_email_is_stored_and_described():
    r = post(mail("0068_new"))
    body = r.json()
    assert r.status_code == 200 and body["stored"] and not body["duplicate"] and body["kind"] == "new"
    assert body["invoiceId"] == "INV2-Z8TH-XHHH-UAP8-TDU2" and body["invoice"]["amount"] == "100.00"
    assert [e.kind for e in rows()] == ["new"]


def test_the_same_email_twice_is_stored_once():
    assert post(mail("0068_new")).json()["stored"] is True
    again = post(mail("0068_new")).json()
    assert again["stored"] is False and again["duplicate"] is True and len(rows()) == 1


def test_issue_and_update_are_two_events_of_one_invoice_in_order():
    post(mail("0068_new")), post(mail("0068_updated"))
    saved = rows()
    assert [e.kind for e in saved] == ["new", "updated"] and {e.invoice_id for e in saved} == {"INV2-Z8TH-XHHH-UAP8-TDU2"}
    assert saved[0].normalized["amount"] == "100.00" and saved[1].normalized["amount"] == "175.00"
    assert saved[0].normalized["note"] == "A to B v0" and saved[1].normalized["note"] is None


def test_two_update_emails_that_look_alike_are_both_kept():
    """A note-only edit does not change anything the email shows, so only the delivery id tells the sends apart."""
    one = mail("0068_updated")
    two = one.replace("0a8d1f3e-d51b-11f1-b650-3f5ff127becb", "ffffffff-d51b-11f1-b650-3f5ff127becb")
    post(one), post(two)
    assert len(rows()) == 2


def test_nothing_with_a_tracking_id_or_the_html_is_kept():
    post(mail("0068_new"))
    saved = rows()[0]
    dump = str(saved.normalized) + str(saved.links)
    for secret_part in ("cust=", "unptid", "utm_", "<", "3P96FTK52PEU6"):
        assert secret_part not in dump
    assert saved.links[0]["url"] == "https://www.sandbox.paypal.com/invoice/payerView/details/INV2-Z8TH-XHHH-UAP8-TDU2"


def test_the_issuer_confirmation_is_refused():
    assert post(mail("issuer_copy")).status_code == 422 and not rows()


def test_text_that_is_not_an_invoice_email_is_refused():
    assert post("hello there").status_code == 422 and post("").status_code == 422 and not rows()


def test_a_forged_look_alike_with_a_foreign_link_is_still_recorded_with_the_link_flagged():
    forged = mail("0068_new").replace("https://www.sandbox.paypal.com/invoice/payerView/details/", "https://paypal-invoices.example/pay/", 1)
    body = post(forged).json()
    assert body["stored"] and body["invoiceId"].startswith("email-")  # no trusted id
    assert any(l["isPaypal"] is False and l["host"] == "paypal-invoices.example" for l in body["links"])


def test_oversized_body_is_refused():
    r = client.post("/inbound/email", content=b"a" * (MAX_HTML * 4 + 1), headers=HEAD)
    assert r.status_code == 413 and not rows()


def labels(body):
    return {f["label"] for f in body["check"]["findings"]}


def test_an_update_that_raised_the_amount_is_judged_against_the_first_email():
    first = post(mail("0068_new")).json()
    second = post(mail("0068_updated")).json()
    assert "Amount raised after sending" not in labels(first)
    assert "Amount raised after sending" in labels(second) and second["check"]["level"] in ("medium", "high")
    assert any(row["field"] == "Amount (earlier email)" for row in second["check"]["comparison"])


def test_both_emails_of_an_invoice_keep_one_entry_in_history():
    post(mail("0068_new")), post(mail("0068_updated"))
    history = [h for h in client.get("/checks").json() if h["invoice"]["number"] == "0068"]
    assert len(history) == 1 and history[0]["invoice"]["amount"] == 175.0


def test_a_forged_email_is_high_because_of_its_link():
    forged = mail("0068_new").replace("https://www.sandbox.paypal.com/invoice/payerView/details/", "https://paypal-invoices.example/pay/", 1)
    body = post(forged).json()
    assert "Payment link does not lead to PayPal" in labels(body) and body["check"]["level"] == "high"


def test_a_repeated_email_returns_the_earlier_result_without_new_findings():
    first = post(mail("0068_new")).json()
    again = post(mail("0068_new")).json()
    assert again["duplicate"] and again["check"]["id"] == first["check"]["id"] and again["check"]["level"] == first["check"]["level"]


def test_a_note_only_update_is_called_out():
    post(mail("0068_new"))
    same = mail("0068_updated").replace("$175.00", "$100.00")
    assert "Updated, but nothing visible changed" in labels(post(same).json())


# --- payment page against the emails of the same invoice -------------------------------------------------------

import json

PAGE = json.loads((Path(__file__).parent / "fixtures/payer_pages/0006_dba.json").read_text())
PAGE_ID = "INV2-HHT8-PAHY-B2ZN-N25L"  # the id inside the page address


def email_for_page(kind="0068_new", amount="110.00", due="Nov 11, 2026", note="ScamCopilot sandbox test"):
    html = mail(kind).replace("INV2-Z8TH-XHHH-UAP8-TDU2", PAGE_ID).replace("$100.00", f"${amount}").replace("$175.00", f"${amount}")
    return html.replace("Nov 14, 2026", due).replace("A to B v0", note)


def check_page(**edits):
    text = PAGE["text"]
    for old, new in edits.items():
        text = text.replace(old.replace("__", " "), new)
    return client.post("/checks/page", json={"url": PAGE["url"], "text": text}).json()


def page_labels(body):
    return {f["label"] for f in body["findings"]}


def test_a_page_that_matches_its_emails_says_so():
    post(email_for_page())
    assert "Page matches the emails" in page_labels(check_page())


def test_a_note_changed_after_the_email_is_found_on_the_page():
    post(email_for_page())
    body = check_page(**{"ScamCopilot__sandbox__test": "Call 1-888-555-0142 to cancel"})
    assert {"Seller's note changed after the email", "Phone number in invoice text"} <= page_labels(body)
    assert any("ScamCopilot sandbox test" in e and "1-888-555-0142" in e for e in body["evidence"])


def test_the_note_is_compared_with_the_email_that_showed_one_not_with_the_update_that_did_not():
    post(email_for_page())
    post(email_for_page("0068_updated"))  # the update email has no note at all
    body = check_page(**{"ScamCopilot__sandbox__test": "Call 1-888-555-0142 to cancel"})
    assert "Seller's note changed after the email" in page_labels(body)


def test_a_page_amount_that_differs_from_the_last_email_is_high():
    post(email_for_page())
    body = check_page(**{"110.00": "250.00"})
    f = next(f for f in body["findings"] if f["label"] == "Page amount differs from the last email")
    assert f["severity"] == "high"
    assert any("250.00" in e and "110.00" in e for e in body["evidence"])


def test_a_note_the_first_email_did_not_show_is_reported_as_such():
    html = email_for_page().replace("Note from seller", "Seller remarks")
    post(html)
    assert "Page has a note the first email did not show" in page_labels(check_page())


def test_without_any_email_the_page_is_checked_as_before():
    labels_ = page_labels(check_page())
    assert not any(l.startswith("Page ") or "after the email" in l for l in labels_)


def test_a_duplicate_is_judged_again_with_current_rules_not_answered_from_the_stored_verdict():
    first = post(mail("0068_new")).json()
    with SessionLocal() as db:  # make the stored verdict look like one written by older rules
        row = db.scalars(select(Check)).one()
        row.result = {**row.result, "findings": [{"id": "old", "label": "Old rule", "severity": "high"}], "level": "high"}
        db.commit()
    again = post(mail("0068_new")).json()
    assert again["duplicate"] and not again["stored"] and len(rows()) == 1
    assert again["check"]["id"] == first["check"]["id"]
    assert all(f["id"] != "old" and f.get("detail") for f in again["check"]["findings"])

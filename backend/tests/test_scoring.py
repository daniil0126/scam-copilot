from datetime import date, timedelta
from types import SimpleNamespace

from app.scoring import score_invoice

FUTURE = (date.today() + timedelta(days=14)).isoformat()


def invoice(name="Acme Supplies Ltd.", email="billing@acme.example.com", amount=100.0, note="", due=FUTURE):
    return {"number": "1", "supplier": {"name": name, "email": email, "phone": ""}, "amount": amount,
            "currency": "USD", "dueDate": due, "note": note, "status": "SENT"}


def past(name="Acme Supplies Ltd.", email="billing@acme.example.com", amount=100.0):
    return SimpleNamespace(supplier_name=name, supplier_email=email, amount=amount, currency="USD")


def labels(r):
    return {f["label"] for f in r["findings"]}


def test_clean_first_invoice_is_low():
    r = score_invoice(invoice(), None, None)
    assert r["level"] == "low" and labels(r) == {"New supplier"}


def test_repeat_supplier_same_amount_is_low_with_no_warnings():
    r = score_invoice(invoice(), past(), None)
    assert r["level"] == "low" and r["score"] == 0


def test_amount_up_30_percent_is_flagged_medium_finding():
    r = score_invoice(invoice(amount=130), past(), None)
    assert "Amount mismatch" in labels(r)


def test_amount_more_than_doubled_is_at_least_medium():
    r = score_invoice(invoice(amount=500), past(), None)
    assert "Amount far from usual" in labels(r) and r["level"] != "low"


def test_payment_email_swap_is_high():
    r = score_invoice(invoice(email="pay@acme-supp1ies.example.com"), past(), None)
    assert r["level"] == "high" or "Payment email changed" in labels(r)
    assert r["score"] >= 45


def test_same_paypal_new_name_is_medium():
    r = score_invoice(invoice(name="Totally New Name"), None, past())
    assert "Supplier name changed" in labels(r) and r["level"] == "medium"


def test_scam_text_with_phone_is_high():
    note = "Your subscription was renewed. If unauthorized call 1-888-555-0142 to cancel and get a refund."
    r = score_invoice(invoice(name="Norton Security", email="x@mail-pay.example.com", amount=499, note=note), None, None)
    assert r["level"] == "high" and r["score"] == 100
    assert {"Phone number in invoice text", "Suspicious wording"} <= labels(r)


def test_brand_with_matching_domain_is_not_impersonation():
    r = score_invoice(invoice(name="Norton Security", email="billing@norton.com"), None, None)
    assert not any("impersonation" in l for l in labels(r))


def test_brand_with_foreign_domain_is_impersonation():
    r = score_invoice(invoice(name="Amazon Support", email="a@gmail.com"), None, None)
    assert "Possible Amazon impersonation" in labels(r)


def test_link_in_note_is_flagged():
    assert "Link in invoice text" in labels(score_invoice(invoice(note="pay at http://x.example"), past(), None))


def test_missing_due_date_is_flagged():
    assert "No due date" in labels(score_invoice(invoice(due=""), past(), None))


def test_overdue_is_flagged():
    old = (date.today() - timedelta(days=3)).isoformat()
    assert "Overdue invoice" in labels(score_invoice(invoice(due=old), past(), None))


def test_large_amount_from_unknown_sender():
    assert "Large amount from unknown sender" in labels(score_invoice(invoice(amount=300), None, None))
    assert "Large amount from unknown sender" not in labels(score_invoice(invoice(amount=299), None, None))


def test_score_is_capped_at_100():
    note = "call 1-888-555-0142 cancel refund unauthorized http://x.example"
    assert score_invoice(invoice(name="Norton", email="a@b.example", amount=900, note=note, due=""), None, None)["score"] == 100


def test_zero_previous_amount_does_not_crash():
    assert score_invoice(invoice(amount=50), past(amount=0), None)["level"] == "low"


def test_a_field_the_source_does_not_show_is_not_a_difference():
    # an invoice email has no seller PayPal email: empty against a known one must not read as "differs"
    result = score_invoice(invoice(email=""), past(), None)
    rows = {r["field"]: r for r in result["comparison"]}
    assert rows["PayPal email"]["differs"] is False


def test_findings_carry_their_explanation():
    result = score_invoice(invoice(amount=140.0), past(), None)
    assert all(f["detail"] for f in result["findings"])


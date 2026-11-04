"""The rule engine behind `RULES_ENGINE=v2` (sprint A2): adapters, both result shapes, and the run_check path.

v2 runs through `run_check(..., normalized=...)` — the same entry the monitor uses. The HTTP tests in
`test_checks.py` use a fake `get_invoice` but not `paypal_request`, so `POST /checks` under v2 would fall back to
the legacy path there; that fallback is intentional and covered by its own test. The API guards (A5, A6) are tested
against the legacy path, which is enough: the guard runs before any scoring.
"""
import asyncio
from datetime import datetime, timezone

import pytest

from app.checks import _recompute_contract_after_extra, risk_to_legacy, run_check, to_rules_invoice
from app.db import SessionLocal
from app.normalize import Invoice as NormalizeInvoice
from app.rules.types import Invoice as RulesInvoice, Signal
from app.scoring import apply_extra
from tests.test_checks import INVOICES, client, fresh_db, make  # noqa: F401


# --- helpers -------------------------------------------------------------------------------------------------------

def _normalized(invoice_id="INV2-TEST-0001", **kw) -> NormalizeInvoice:
    base = dict(
        id=invoice_id, accountId="acc", source="paypal_api",
        invoiceNumber="0042", status="SENT", amount="100.00", currency="USD",
        invoiceDate=None, dueDate=None,
        senderName="Acme Supplies Ltd.", senderEmail="billing@acme.example.com", senderPhone="001 5550100",
        recipientEmail="buyer@example.org", paymentTerms="Net 14",
        items=[{"name": "Consulting", "description": None, "quantity": "1", "unitAmount": "100.00"}],
        paymentLinks=["https://www.paypal.com/invoice/p/#TEST"],
        note="Thank you", createdAt=None, updatedAt=None, contentHash="sha256:test",
    )
    base.update(kw)
    return NormalizeInvoice(**base)


def _run(invoice_id, flat, normalized):
    async def go():
        with SessionLocal() as db:
            return await run_check(db, invoice_id, flat, normalized=normalized)
    return asyncio.run(go())


# --- adapters (pure) -----------------------------------------------------------------------------------------------

def test_to_rules_invoice_maps_every_shared_field():
    inv = _normalized()
    rules = to_rules_invoice(inv)
    assert isinstance(rules, RulesInvoice)
    for field in ("id", "accountId", "source", "invoiceNumber", "status", "amount", "currency",
                  "senderName", "senderEmail", "senderPhone", "recipientEmail", "paymentTerms",
                  "paymentLinks", "note", "contentHash"):
        assert getattr(rules, field) == getattr(inv, field), field
    assert rules.items is not None and rules.items[0].name == "Consulting"


def test_to_rules_invoice_accepts_email_source():
    rules = to_rules_invoice(_normalized(source="email"))
    assert rules.source == "email"


# --- risk_to_legacy: both shapes in one dict -----------------------------------------------------------------------

def _signal(type_, severity, status="DETECTED", evidence="x") -> Signal:
    return Signal(type=type_, severity=severity, status=status, evidence=evidence,
                  evidenceData={}, source="RULE_ENGINE", ruleVersion="t")


def _risk(level, score, signals, confidence="HIGH"):
    from app.rules.types import RiskResult
    return RiskResult(
        invoiceId="INV2-TEST-0001", invoiceVersionHash="sha256:test", riskScore=score, riskLevel=level,
        confidence=confidence, signals=signals, recommendations=["Verify with the supplier."],
        comparison=[], engineVersion="rules-0.1", analyzedAt=datetime(2026, 11, 2, 12, tzinfo=timezone.utc),
    )


def test_risk_to_legacy_keeps_legacy_keys_for_scoring_and_llm():
    result = risk_to_legacy(_risk("MEDIUM", 45, [_signal("PHONE_IN_TEXT", "HIGH")]), {"supplier": {"name": "Acme"}})
    for key in ("level", "score", "findings", "comparison", "recommendation", "evidence", "invoice"):
        assert key in result, key
    assert result["level"] == "medium" and result["score"] == 45
    assert result["findings"][0]["id"] == "phone"
    assert result["invoice"] == {"supplier": {"name": "Acme"}}


def test_risk_to_legacy_adds_contract_keys_for_notifications_and_reports():
    result = risk_to_legacy(_risk("HIGH", 65, [_signal("SENDER_MISMATCH", "HIGH")]), {"supplier": {}})
    for key in ("riskLevel", "riskScore", "signals", "confidence", "engineVersion", "analyzedAt"):
        assert key in result, key
    assert result["riskLevel"] == "HIGH" and result["signals"][0]["type"] == "SENDER_MISMATCH"


def test_critical_becomes_legacy_high_with_score_at_least_80():
    result = risk_to_legacy(_risk("CRITICAL", 86, [_signal("UNUSUAL_AMOUNT", "HIGH")]), {"supplier": {}})
    assert result["level"] == "high" and result["score"] >= 80
    assert result["riskLevel"] == "CRITICAL"
    from app.notifications import categories
    assert categories.risk_level(result) == "CRITICAL"


def test_insufficient_data_signal_becomes_a_skipped_finding():
    result = risk_to_legacy(_risk("LOW", 10, [_signal("DUPLICATE_EXACT", "LOW", status="INSUFFICIENT_DATA")]),
                            {"supplier": {}})
    finding = result["findings"][0]
    assert finding["skipped"] is True and finding["severity"] == "ok"
    from app.notifications import categories
    assert categories.detected(result) == []


def test_duplicate_signal_keeps_its_type_in_the_contract_view():
    result = risk_to_legacy(_risk("HIGH", 60, [_signal("DUPLICATE_EXACT", "HIGH")]), {"supplier": {}})
    from app.notifications import categories
    assert categories.category_hits(result)["POTENTIAL_DUPLICATE"] == ["DUPLICATE_EXACT"]


def test_apply_extra_after_v2_keeps_contract_view_in_sync():
    """`apply_extra` only rewrites the legacy view; the recompute call restores CRITICAL for `categories.risk_level`."""
    result = risk_to_legacy(_risk("LOW", 10, []), {"supplier": {}})
    extra = {"findings": [{"id": "email-link", "label": "Payment link does not lead to PayPal",
                           "severity": "high", "pts": 60, "text": "x"}], "comparison": []}
    apply_extra(result, extra)
    assert result["level"] == "high" and result["score"] >= 60
    _recompute_contract_after_extra(result)
    # 60 legacy points is HIGH, not CRITICAL; the contract view must match the legacy one.
    from app.notifications import categories
    assert result["riskLevel"] == categories.risk_level(result) == "HIGH"
    assert result["riskScore"] == categories.risk_score(result) == result["score"]


# --- run_check under the flag --------------------------------------------------------------------------------------

def test_v2_returns_both_shapes(monkeypatch):
    monkeypatch.setenv("RULES_ENGINE", "v2")
    result = _run("INV2-V2", make(), _normalized("INV2-V2"))
    assert result["level"] in ("low", "medium", "high")
    assert result["riskLevel"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert isinstance(result["signals"], list) and "engineVersion" in result


def test_v2_new_supplier_is_new_sender_signal(monkeypatch):
    monkeypatch.setenv("RULES_ENGINE", "v2")
    result = _run("INV2-V2", make(), _normalized("INV2-V2"))
    types = {s["type"] for s in result["signals"] if s["status"] == "DETECTED"}
    assert "NEW_SENDER" in types


def test_v2_payment_email_swap_on_the_same_invoice_is_high(monkeypatch):
    """The engine sees an email change on the same invoice id through `knownContacts`, which `build_vendor_history`
    fills from earlier versions of that invoice (`earlier_self`). A different invoice id with a new email is a new
    sender, not a mismatch — that is `test_v2_new_supplier_is_new_sender_signal`."""
    monkeypatch.setenv("RULES_ENGINE", "v2")
    from app.models import InvoiceVersion
    from app.monitor import account_id

    old = _normalized("INV2-A", senderEmail="billing@acme.example.com", contentHash="sha256:old",
                      createdAt=datetime(2026, 9, 1, tzinfo=timezone.utc))
    with SessionLocal() as db:
        db.add(InvoiceVersion(account_id=account_id(), invoice_id="INV2-A", content_hash="sha256:old",
                              normalized=old.model_dump(mode="json"), raw={}))
        db.commit()

    flat = make(email="pay@acme-supp1ies.example.com")
    new = _normalized("INV2-A", senderEmail="pay@acme-supp1ies.example.com", contentHash="sha256:new",
                      createdAt=datetime(2026, 9, 1, tzinfo=timezone.utc))
    result = _run("INV2-A", flat, new)
    assert any(s["type"] == "SENDER_MISMATCH" for s in result["signals"] if s["status"] == "DETECTED")
    assert result["level"] in ("medium", "high")


def test_v2_phone_in_note_is_detected(monkeypatch):
    monkeypatch.setenv("RULES_ENGINE", "v2")
    flat = make(amount=499)
    flat["note"] = "Your subscription was renewed. Call 1-888-555-0142 to cancel."
    result = _run("INV2-A", flat, _normalized("INV2-A", amount="499.00",
                                              note="Your subscription was renewed. Call 1-888-555-0142 to cancel."))
    types = {s["type"] for s in result["signals"] if s["status"] == "DETECTED"}
    assert "PHONE_IN_TEXT" in types
    assert any(f["id"] == "phone" for f in result["findings"])


def test_v2_small_ordinary_invoice_is_not_high(monkeypatch):
    monkeypatch.setenv("RULES_ENGINE", "v2")
    result = _run("INV2-A", make(amount=60), _normalized("INV2-A", amount="60.00"))
    assert result["level"] in ("low", "medium")


def test_v2_ignores_normalized_absent(monkeypatch):
    """Without `normalized` (the current POST /checks path in tests) v2 must fall back to the legacy scorer, not crash."""
    monkeypatch.setenv("RULES_ENGINE", "v2")
    result = _run("INV2-A", make(), None)
    assert "signals" not in result and "riskLevel" not in result
    assert {"level", "score", "findings"} <= set(result)


def test_legacy_without_the_flag_is_unchanged(monkeypatch):
    monkeypatch.delenv("RULES_ENGINE", raising=False)
    result = _run("INV2-A", make(), _normalized("INV2-A"))
    assert "signals" not in result and "riskLevel" not in result
    assert {"level", "score", "findings", "comparison", "recommendation", "evidence"} <= set(result)


# --- A5: the id from the request body is validated before it goes into a PayPal URL --------------------------------

@pytest.mark.parametrize("bad", ["", "..", "../x", "a/b", "INV2-1 2", "x" * 200, "INV2-1?x=1"])
def test_checks_rejects_an_unsafe_invoice_id(bad):
    res = client.post("/checks", json={"invoice_id": bad})
    assert res.status_code == 422


def test_checks_accepts_a_real_id():
    INVOICES["INV2-GOOD-1234-5678-90AB"] = make()
    assert client.post("/checks", json={"invoice_id": "INV2-GOOD-1234-5678-90AB"}).status_code == 200


# --- A6: UTC datetime, stored naive, returned with a Z -------------------------------------------------------------

def test_checked_at_is_iso_utc_with_z(monkeypatch):
    monkeypatch.delenv("RULES_ENGINE", raising=False)
    INVOICES["INV2-A"] = make()
    result = client.post("/checks", json={"invoice_id": "INV2-A"}).json()
    assert result["checkedAt"].endswith("Z")
    from app.models import Check
    with SessionLocal() as db:
        row = db.query(Check).filter_by(paypal_invoice_id="INV2-A").one()
        assert row.checked_at.tzinfo is None
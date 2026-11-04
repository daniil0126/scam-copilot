from datetime import date, datetime, timezone
from decimal import Decimal

from app.rules.config import RulesConfig
from app.rules.rule_b import rule_b
from app.rules.types import (
    HistoricalInvoice, Invoice, InvoiceItem, VendorHistory,
)

CFG = RulesConfig()


def _inv(**kw) -> Invoice:
    base = dict(id="INV-1", source="paypal_api", contentHash="h")
    base.update(kw)
    return Invoice(**base)


def _h(**kw) -> HistoricalInvoice:
    return HistoricalInvoice(id="h1", **kw)


def test_no_candidates_insufficient():
    sigs = rule_b(_inv(amount=Decimal("100"), currency="USD"), VendorHistory(senderKey="x"), CFG)
    assert len(sigs) == 1
    assert sigs[0].status == "INSUFFICIENT_DATA" and sigs[0].type == "DUPLICATE_EXACT"


def test_exact_duplicate():
    hist = VendorHistory(senderKey="x", otherSenderInvoices=[
        _h(invoiceNumber="A-1", amount="100", currency="USD",
           createdAt=datetime(2026, 1, 1, tzinfo=timezone.utc))
    ])
    inv = _inv(invoiceNumber="A-1", amount=Decimal("100"), currency="USD",
               invoiceDate=date(2026, 1, 1))
    sigs = rule_b(inv, hist, CFG)
    assert any(s.type == "DUPLICATE_EXACT" for s in sigs)


def test_same_amount_alone_not_duplicate():
    hist = VendorHistory(senderKey="x", otherSenderInvoices=[
        _h(invoiceNumber="B-2", amount="100", currency="USD",
           createdAt=datetime(2026, 1, 1, tzinfo=timezone.utc))
    ])
    inv = _inv(invoiceNumber="A-1", amount=Decimal("100"), currency="USD",
               invoiceDate=date(2026, 6, 1))
    sigs = rule_b(inv, hist, CFG)
    assert not any(s.type.startswith("DUPLICATE") and s.status == "DETECTED" for s in sigs)


def test_potential_close_dates():
    # Same amount, close dates AND the same line items: a potential duplicate.
    items = [InvoiceItem(name="Widget", quantity="1", unitAmount="100.00")]
    hist = VendorHistory(senderKey="x", otherSenderInvoices=[
        _h(invoiceNumber="B-2", amount="100", currency="USD", itemsSignature="Widget|1|100.00",
           createdAt=datetime(2026, 1, 1, tzinfo=timezone.utc))
    ])
    inv = _inv(invoiceNumber="A-1", amount=Decimal("100"), currency="USD",
               invoiceDate=date(2026, 1, 2), items=items)
    sigs = rule_b(inv, hist, CFG)
    assert any(s.type == "DUPLICATE_POTENTIAL" for s in sigs)


def test_potential_requires_the_same_items():
    # Same amount and a close date but different items: the next month's invoice, not a duplicate.
    hist = VendorHistory(senderKey="x", otherSenderInvoices=[
        _h(invoiceNumber="B-2", amount="100", currency="USD", itemsSignature="Widget|1|100.00",
           createdAt=datetime(2026, 1, 1, tzinfo=timezone.utc))
    ])
    inv = _inv(invoiceNumber="A-1", amount=Decimal("100"), currency="USD",
               invoiceDate=date(2026, 1, 2),
               items=[InvoiceItem(name="Gadget", quantity="1", unitAmount="100.00")])
    sigs = rule_b(inv, hist, CFG)
    assert not any(s.type == "DUPLICATE_POTENTIAL" for s in sigs)


def test_different_currency_not_duplicate():
    hist = VendorHistory(senderKey="x", otherSenderInvoices=[
        _h(invoiceNumber="B-2", amount="100", currency="EUR",
           createdAt=datetime(2026, 1, 1, tzinfo=timezone.utc))
    ])
    inv = _inv(invoiceNumber="B-2", amount=Decimal("100"), currency="USD",
               invoiceDate=date(2026, 1, 1))
    sigs = rule_b(inv, hist, CFG)
    assert not any(s.type == "DUPLICATE_EXACT" for s in sigs)


def test_similar_items_and_amount():
    items = [InvoiceItem(name="Widget", quantity="1", unitAmount="100.00")]
    hist = VendorHistory(senderKey="x", otherSenderInvoices=[
        _h(invoiceNumber="B-2", amount="100.50", currency="USD",
           itemsSignature="Widget|1|100.00",
           createdAt=datetime(2026, 1, 1, tzinfo=timezone.utc))
    ])
    inv = _inv(invoiceNumber="A-1", amount=Decimal("100"), currency="USD",
               invoiceDate=date(2026, 6, 1), items=items)
    sigs = rule_b(inv, hist, CFG)
    assert any(s.type == "DUPLICATE_SIMILAR" for s in sigs)


def test_prior_invoices_used_too():
    hist = VendorHistory(senderKey="x", priorInvoices=[
        _h(invoiceNumber="A-1", amount="100", currency="USD",
           createdAt=datetime(2026, 1, 1, tzinfo=timezone.utc))
    ])
    inv = _inv(invoiceNumber="A-1", amount=Decimal("100"), currency="USD",
               invoiceDate=date(2026, 1, 1))
    sigs = rule_b(inv, hist, CFG)
    assert any(s.type == "DUPLICATE_EXACT" for s in sigs)

def test_empty_sender_key_insufficient():
    hist = VendorHistory(senderKey="", otherSenderInvoices=[
        _h(invoiceNumber="B-2", amount="100", currency="USD",
           createdAt=datetime(2026, 1, 1, tzinfo=timezone.utc))
    ])
    inv = _inv(invoiceNumber="A-1", amount=Decimal("100"), currency="USD",
               invoiceDate=date(2026, 1, 1))
    sigs = rule_b(inv, hist, CFG)
    assert len(sigs) == 1
    assert sigs[0].status == "INSUFFICIENT_DATA"
    assert sigs[0].evidenceData["senderKey"] is None
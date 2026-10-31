from datetime import datetime, timezone
from decimal import Decimal

from app.rules.rule_a import rule_a
from app.rules.config import RulesConfig
from app.rules.types import Invoice, HistoricalInvoice, VendorHistory


def _invoice(**kw) -> Invoice:
    base = dict(id="INV-1", source="paypal_api", contentHash="h1")
    base.update(kw)
    return Invoice(**base)


def _history(amounts: list[str], currency: str = "USD") -> VendorHistory:
    return VendorHistory(
        senderKey="vendor@example.com",
        priorInvoices=[
            HistoricalInvoice(id=f"h{i}", amount=a, currency=currency,
                              createdAt=datetime(2026, 1, i + 1, tzinfo=timezone.utc))
            for i, a in enumerate(amounts)
        ],
        totalCount=len(amounts), complete=True,
    )


CFG = RulesConfig()


def test_amount_missing_returns_insufficient():
    sigs = rule_a(_invoice(amount=None), _history(["10", "20", "30"]), CFG)
    assert len(sigs) == 1 and sigs[0].status == "INSUFFICIENT_DATA"


def test_amount_currency_missing_returns_insufficient():
    sigs = rule_a(_invoice(amount="100", currency=None),
                       _history(["10", "20", "30"]), CFG)
    assert sigs[0].status == "INSUFFICIENT_DATA"


def test_amount_short_history_returns_insufficient():
    sigs = rule_a(_invoice(amount="100", currency="USD"),
                       _history(["10", "20"]), CFG)
    assert sigs[0].status == "INSUFFICIENT_DATA"
    assert sigs[0].evidenceData["required"] == CFG.amount_min_history


def test_amount_within_threshold_no_signal():
    # медиана 100, current 200, ratio 2.0 < 2.5
    sigs = rule_a(_invoice(amount="200", currency="USD"),
                       _history(["100", "100", "100"]), CFG)
    assert sigs == []


def test_amount_medium():
    # медиана 100, current 300 → 3.0× → MEDIUM
    sigs = rule_a(_invoice(amount="300", currency="USD"),
                       _history(["100", "100", "100"]), CFG)
    assert len(sigs) == 1
    assert sigs[0].status == "DETECTED" and sigs[0].severity == "MEDIUM"
    assert sigs[0].evidence


def test_amount_high():
    sigs = rule_a(_invoice(amount="600", currency="USD"),
                       _history(["100", "100", "100"]), CFG)
    assert sigs[0].severity == "HIGH"


def test_amount_critical():
    sigs = rule_a(_invoice(amount="2000", currency="USD"),
                       _history(["100", "100", "100"]), CFG)
    assert sigs[0].severity == "CRITICAL"


def test_amount_different_currency_insufficient():
    sigs = rule_a(_invoice(amount="300", currency="EUR"),
                       _history(["100", "100", "100"], currency="USD"), CFG)
    assert sigs[0].status == "INSUFFICIENT_DATA"


def test_amount_boundary_250():
    # ровно на пороге — срабатывает (ratio >= medium)
    sigs = rule_a(_invoice(amount="250", currency="USD"),
                       _history(["100", "100", "100"]), CFG)
    assert len(sigs) == 1 and sigs[0].severity == "MEDIUM"


def test_amount_boundary_249_no_signal():
    sigs = rule_a(_invoice(amount="249", currency="USD"),
                       _history(["100", "100", "100"]), CFG)
    assert sigs == []
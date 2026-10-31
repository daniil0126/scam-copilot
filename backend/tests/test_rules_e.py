from datetime import datetime, timedelta, timezone

from app.rules.rule_e import rule_e
from app.rules.config import RulesConfig
from app.rules.types import HistoricalInvoice, Invoice, VendorHistory

CFG = RulesConfig()


def _inv() -> Invoice:
    return Invoice(id="INV-1", source="paypal_api", contentHash="h")


def _h(days_ago: int, idx: int = 0) -> HistoricalInvoice:
    return HistoricalInvoice(
        id=f"h{idx}", amount="100", currency="USD",
        createdAt=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )


def test_incomplete_history_insufficient():
    h = VendorHistory(senderKey="x", complete=False,
                      priorInvoices=[_h(1, 0), _h(2, 1), _h(3, 2)])
    sigs = rule_e(_inv(), h, CFG)
    assert len(sigs) == 1 and sigs[0].status == "INSUFFICIENT_DATA"


def test_short_history_insufficient():
    h = VendorHistory(senderKey="x", complete=True, priorInvoices=[_h(1, 0)])
    sigs = rule_e(_inv(), h, CFG)
    assert len(sigs) == 1 and sigs[0].status == "INSUFFICIENT_DATA"


def test_burst_detected():
    # 10 инвойсов за последние 3 дня при общей истории 300 дней — всплеск
    hist = [_h(i % 3, i) for i in range(10)] + [_h(d, 100 + d) for d in range(30, 300, 30)]
    h = VendorHistory(senderKey="x", complete=True, priorInvoices=hist)
    sigs = rule_e(_inv(), h, CFG)
    assert any(s.type == "UNUSUAL_SENDER_ACTIVITY" and s.status == "DETECTED" for s in sigs)


def test_normal_activity_no_signal():
    # 3 инвойса за 300 дней — не всплеск
    h = VendorHistory(senderKey="x", complete=True,
                      priorInvoices=[_h(100, 0), _h(200, 1), _h(300, 2)])
    sigs = rule_e(_inv(), h, CFG)
    assert not any(s.status == "DETECTED" for s in sigs)


def test_no_dates_insufficient():
    h = VendorHistory(senderKey="x", complete=True, priorInvoices=[
        HistoricalInvoice(id="h0", amount="100", currency="USD", createdAt=None),
        HistoricalInvoice(id="h1", amount="100", currency="USD", createdAt=None),
        HistoricalInvoice(id="h2", amount="100", currency="USD", createdAt=None),
    ])
    sigs = rule_e(_inv(), h, CFG)
    assert len(sigs) == 1 and sigs[0].status == "INSUFFICIENT_DATA"
from datetime import date, timedelta
from app.rules.config import RulesConfig
from app.rules.rule_due import rule_due
from app.rules.types import Invoice, VendorHistory

CFG = RulesConfig()
H = VendorHistory(senderKey="x")


def _inv(**kw) -> Invoice:
    base = dict(id="INV-1", source="paypal_api", contentHash="h")
    base.update(kw)
    return Invoice(**base)


def test_no_due_date():
    sigs = rule_due(_inv(dueDate=None), H, CFG)
    assert len(sigs) == 1 and sigs[0].evidenceData["reason"] == "missing"


def test_overdue():
    sigs = rule_due(_inv(dueDate=date.today() - timedelta(days=1)), H, CFG)
    assert len(sigs) == 1 and sigs[0].evidenceData["reason"] == "overdue"


def test_future_due_ok():
    assert rule_due(_inv(dueDate=date.today() + timedelta(days=7)), H, CFG) == []
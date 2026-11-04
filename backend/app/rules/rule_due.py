from __future__ import annotations

from datetime import date

from .config import RulesConfig
from .types import Invoice, Signal, VendorHistory


RULE_VERSION_SUFFIX = "due"


def rule_due(invoice: Invoice, history: VendorHistory, config: RulesConfig) -> list[Signal]:
    """The due date is a fact about the invoice, not a risk on its own.

    Severity is LOW (10 points): a missing or overdue due date matters when it comes with other signs, but on its
    own it is common in ordinary invoices and in invoices with little data (legacy gives it 10 points for the same
    reason). MEDIUM here would push a single missing date to the MEDIUM band once `SEVERITY_POINTS['MEDIUM']` is 30.
    """
    rule_version = f"{RULE_VERSION_SUFFIX}-{config.version}"

    if invoice.dueDate is None:
        return [Signal(
            type="DUE_DATE_ISSUE", severity="LOW", status="DETECTED",
            evidence="В инвойсе нет срока оплаты (due date)",
            evidenceData={"dueDate": None, "reason": "missing"},
            source="RULE_ENGINE", ruleVersion=rule_version,
        )]

    if invoice.dueDate < date.today():
        return [Signal(
            type="DUE_DATE_ISSUE", severity="LOW", status="DETECTED",
            evidence=f"Срок оплаты {invoice.dueDate.isoformat()} уже прошёл",
            evidenceData={"dueDate": invoice.dueDate.isoformat(), "reason": "overdue"},
            source="RULE_ENGINE", ruleVersion=rule_version,
        )]

    return []
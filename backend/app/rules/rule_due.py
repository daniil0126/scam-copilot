from __future__ import annotations

from datetime import date

from .config import RulesConfig
from .types import Invoice, Signal, VendorHistory


RULE_VERSION_SUFFIX = "due"


def rule_due(invoice: Invoice, history: VendorHistory, config: RulesConfig) -> list[Signal]:
    rule_version = f"{RULE_VERSION_SUFFIX}-{config.version}"

    if invoice.dueDate is None:
        return [Signal(
            type="DUE_DATE_ISSUE", severity="MEDIUM", status="DETECTED",
            evidence="В инвойсе нет срока оплаты (due date)",
            evidenceData={"dueDate": None, "reason": "missing"},
            source="RULE_ENGINE", ruleVersion=rule_version,
        )]

    if invoice.dueDate < date.today():
        return [Signal(
            type="DUE_DATE_ISSUE", severity="MEDIUM", status="DETECTED",
            evidence=f"Срок оплаты {invoice.dueDate.isoformat()} уже прошёл",
            evidenceData={"dueDate": invoice.dueDate.isoformat(), "reason": "overdue"},
            source="RULE_ENGINE", ruleVersion=rule_version,
        )]

    return []
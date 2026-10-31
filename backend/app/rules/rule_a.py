from __future__ import annotations

from decimal import Decimal
from statistics import median

from .config import RulesConfig
from .types import Invoice, Signal, VendorHistory


RULE_VERSION_SUFFIX = "amount"


def _median_same_currency(invoice: Invoice, history: VendorHistory) -> Decimal | None:
    """Медиана сумм прошлых инвойсов в той же валюте. None, если сравнивать не с чем."""
    if invoice.currency is None:
        return None
    values = []
    for h in history.priorInvoices:
        if h.amount is None or h.currency is None:
            continue
        if h.currency.upper() != invoice.currency.upper():
            continue
        try:
            values.append(Decimal(h.amount))
        except Exception:
            continue
    if not values:
        return None
    return median(values)


def rule_a(
    invoice: Invoice, history: VendorHistory, config: RulesConfig
) -> list[Signal]:
    rule_version = f"{RULE_VERSION_SUFFIX}-{config.version}"

    if invoice.amount is None:
        return [Signal(
            type="UNUSUAL_AMOUNT", severity="LOW", status="INSUFFICIENT_DATA",
            evidence="amount отсутствует в инвойсе",
            evidenceData={}, source="RULE_ENGINE", ruleVersion=rule_version,
        )]

    if invoice.currency is None:
        return [Signal(
            type="UNUSUAL_AMOUNT", severity="LOW", status="INSUFFICIENT_DATA",
            evidence="currency отсутствует — сравнение с историей невозможно",
            evidenceData={}, source="RULE_ENGINE", ruleVersion=rule_version,
        )]

    if len(history.priorInvoices) < config.amount_min_history:
        return [Signal(
            type="UNUSUAL_AMOUNT", severity="LOW", status="INSUFFICIENT_DATA",
            evidence=f"история поставщика {len(history.priorInvoices)} < {config.amount_min_history}",
            evidenceData={"historyCount": len(history.priorInvoices),
                          "required": config.amount_min_history},
            source="RULE_ENGINE", ruleVersion=rule_version,
        )]

    med = _median_same_currency(invoice, history)
    if med is None or med == 0:
        return [Signal(
            type="UNUSUAL_AMOUNT", severity="LOW", status="INSUFFICIENT_DATA",
            evidence="нет сравнимой истории в той же валюте" + (" (медиана равна нулю)" if med == 0 else ""),
            evidenceData={"currency": invoice.currency, "median": str(med) if med is not None else None},
            source="RULE_ENGINE", ruleVersion=rule_version,
        )]

    ratio = float(invoice.amount) / float(med)
    if ratio < config.amount_ratio_medium:
        return []  # сигнал не создаётся

    if ratio >= config.amount_ratio_critical:
        severity = "CRITICAL"
    elif ratio >= config.amount_ratio_high:
        severity = "HIGH"
    else:
        severity = "MEDIUM"

    return [Signal(
        type="UNUSUAL_AMOUNT", severity=severity, status="DETECTED",
        evidence=f"{invoice.amount} {invoice.currency} против медианы {med} {invoice.currency} (×{ratio:.2f})",
        evidenceData={
            "current": str(invoice.amount),
            "historicalMedian": str(med),
            "ratio": round(ratio, 2),
            "refInvoiceIds": [h.id for h in history.priorInvoices[:5]],
        },
        source="RULE_ENGINE", ruleVersion=rule_version,
    )]
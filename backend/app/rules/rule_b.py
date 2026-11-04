from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from .config import RulesConfig
from .types import HistoricalInvoice, Invoice, Signal, VendorHistory


RULE_VERSION_SUFFIX = "duplicates"


def _dec(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _same_amount(invoice: Invoice, h: HistoricalInvoice) -> tuple[bool, Decimal | None, Decimal | None]:
    current = invoice.amount
    if current is None or h.amount is None:
        return False, None, None
    if not invoice.currency or not h.currency:
        return False, None, None
    if invoice.currency.upper() != h.currency.upper():
        return False, None, None
    h_amount = _dec(h.amount)
    if h_amount is None:
        return False, None, None
    return current == h_amount, current, h_amount


def _days_between(a: datetime | None, b: datetime | None) -> int | None:
    if a is None or b is None:
        return None
    if a.tzinfo is None:
        a = a.replace(tzinfo=timezone.utc)
    if b.tzinfo is None:
        b = b.replace(tzinfo=timezone.utc)
    return abs((a - b).days)


def _items_signature(invoice: Invoice) -> str | None:
    """Строковая сигнатура позиций инвойса: имена+количества+цены, без учёта порядка."""
    if not invoice.items:
        return None
    parts = []
    for item in invoice.items:
        parts.append(f"{item.name or ''}|{item.quantity or ''}|{item.unitAmount or ''}")
    return ";;".join(sorted(parts))


def rule_b(invoice: Invoice, history: VendorHistory, config: RulesConfig) -> list[Signal]:
    rule_version = f"{RULE_VERSION_SUFFIX}-{config.version}"

    if not history.senderKey:
        return [Signal(
            type="DUPLICATE_EXACT", severity="LOW", status="INSUFFICIENT_DATA",
            evidence="Нет ключа отправителя — сравнение дубликатов невозможно",
            evidenceData={"senderKey": None},
            source="RULE_ENGINE", ruleVersion=rule_version,
        )]

    candidates = [*history.priorInvoices, *history.otherSenderInvoices]

    if not candidates:
        return [Signal(
            type="DUPLICATE_EXACT", severity="LOW", status="INSUFFICIENT_DATA",
            evidence="Нет других инвойсов для сравнения",
            evidenceData={"priorInvoices": 0, "otherSenderInvoices": 0},
            source="RULE_ENGINE", ruleVersion=rule_version,
        )]

    signals: list[Signal] = []
    current_date = invoice.createdAt or (
        datetime.combine(invoice.invoiceDate, datetime.min.time(), tzinfo=timezone.utc)
        if invoice.invoiceDate else None
    )
    current_sig = _items_signature(invoice)

    for h in candidates:
        same_amount, cur_amt, h_amt = _same_amount(invoice, h)

        # EXACT: same number + same amount + currency + close date
        if invoice.invoiceNumber and h.invoiceNumber and invoice.invoiceNumber == h.invoiceNumber and same_amount:
            diff = _days_between(current_date, h.createdAt)
            if diff is None or diff <= config.duplicate_date_window_days:
                signals.append(Signal(
                    type="DUPLICATE_EXACT", severity="HIGH", status="DETECTED",
                    evidence=f"Тот же номер {invoice.invoiceNumber} и сумма {cur_amt} {invoice.currency}",
                    evidenceData={"refInvoiceId": h.id, "invoiceNumber": invoice.invoiceNumber,
                                  "daysDiff": diff},
                    source="RULE_ENGINE", ruleVersion=rule_version,
                ))
                continue

        # POTENTIAL: same amount + close date + the same line items (or both invoices have no items at all).
        # Without the items check, a monthly subscription with the same amount and a close date (every scenario
        # in scripts/scenarios.py is created within seconds of the previous one) is reported as a duplicate.
        # The items signature is what tells "the same invoice again" apart from "the next month's invoice".
        if same_amount:
            diff = _days_between(current_date, h.createdAt)
            items_match = current_sig is not None and current_sig == h.itemsSignature
            if diff is not None and diff <= config.duplicate_date_window_days and items_match:
                signals.append(Signal(
                    type="DUPLICATE_POTENTIAL", severity="MEDIUM", status="DETECTED",
                    evidence=f"Та же сумма {cur_amt} {invoice.currency} и те же позиции в пределах {diff} дн.",
                    evidenceData={"refInvoiceId": h.id, "daysDiff": diff},
                    source="RULE_ENGINE", ruleVersion=rule_version,
                ))
                continue

        # SIMILAR: same items signature + amount within tolerance
        if (current_sig and h.itemsSignature and current_sig == h.itemsSignature
                and cur_amt is not None and h_amt is not None and h_amt != 0):
            ratio = abs(cur_amt - h_amt) / h_amt
            if ratio <= Decimal(str(config.duplicate_amount_tolerance_pct)):
                signals.append(Signal(
                    type="DUPLICATE_SIMILAR", severity="LOW", status="DETECTED",
                    evidence=f"Похожие позиции и сумма в пределах {config.duplicate_amount_tolerance_pct:.0%}",
                    evidenceData={"refInvoiceId": h.id, "ratio": float(ratio)},
                    source="RULE_ENGINE", ruleVersion=rule_version,
                ))

    return signals
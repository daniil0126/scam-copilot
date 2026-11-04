from __future__ import annotations

from datetime import datetime, timezone

from .config import RulesConfig
from .types import (
    ComparisonRow, HistoricalInvoice, Invoice, RiskResult, Signal, VendorHistory,
)


FAMILY_BY_SIGNAL: dict[str, str] = {
    "UNUSUAL_AMOUNT": "amount",
    "DUPLICATE_EXACT": "duplicates",
    "DUPLICATE_POTENTIAL": "duplicates",
    "DUPLICATE_SIMILAR": "duplicates",
    "SENDER_MISMATCH": "vendor_identity",
    "SENDER_NAME_CHANGED": "vendor_identity",
    "NEW_SENDER": "vendor_identity",
    "SUSPICIOUS_LINK": "links",
    "UNUSUAL_SENDER_ACTIVITY": "activity",
    "BRAND_IMPERSONATION": "textual",
    "PHONE_IN_TEXT": "textual",
    "SCAM_WORDING": "textual",
    "DUE_DATE_ISSUE": "textual",
}

# MEDIUM is 30 so one MEDIUM signal reaches the MEDIUM band on its own. HIGH stays at 40 and CRITICAL at 60:
# with `family_decay` 0.5 and equal family weights, one HIGH signal scores 40 (MEDIUM), two HIGH signals in the
# same family score 60 (HIGH), three score 70, and only a CRITICAL signal (60) or a combination across families
# reaches the CRITICAL band. Raising HIGH to 60 was tried and rejected: on the dataset it dropped precision at
# HIGH from 100% to 57.7% and pushed FPR at HIGH to 32.4% (see docs/plans/engine-comparison.md).
SEVERITY_POINTS: dict[str, int] = {
    "LOW": 10,
    "MEDIUM": 30,
    "HIGH": 40,
    "CRITICAL": 60,
}

RECOMMENDATION_BY_TYPE: dict[str, str] = {
    "UNUSUAL_AMOUNT": "Сумма нетипично высокая для этого поставщика — проверьте, ожидали ли вы такой счёт.",
    "DUPLICATE_EXACT": "Этот инвойс выглядит как точная копия предыдущего — не оплачивайте дважды.",
    "DUPLICATE_POTENTIAL": "Похожий инвойс уже был — убедитесь, что это не повтор.",
    "DUPLICATE_SIMILAR": "Похожие позиции уже встречались — сверьте с прошлым счётом.",
    "SENDER_MISMATCH": "Платёжные реквизиты отличаются от прошлых — свяжитесь с поставщиком по официальному каналу.",
    "SENDER_NAME_CHANGED": "Поставщик сменил имя на том же аккаунте — уточните причину.",
    "NEW_SENDER": "Это первый счёт от данного поставщика — проверьте его, прежде чем платить.",
    "SUSPICIOUS_LINK": "В инвойсе есть подозрительная ссылка — не переходите по ней, откройте сайт поставщика вручную.",
    "UNUSUAL_SENDER_ACTIVITY": "Поставщик резко увеличил число инвойсов — возможен взлом аккаунта.",
    "BRAND_IMPERSONATION": "Имя поставщика похоже на известный бренд, но домен чужой — возможна подмена.",
    "PHONE_IN_TEXT": "В тексте инвойса есть телефон — не звоните по нему, используйте официальные контакты поставщика.",
    "SCAM_WORDING": "В тексте инвойса есть типичные scam-формулировки.",
    "DUE_DATE_ISSUE": "Срок оплаты отсутствует или уже прошёл — это частый признак давления.",
}

MAX_SCORE = 100


def _family_points(signals_of_family: list[Signal], config: RulesConfig) -> float:
    """Убывающий вклад: max + decay * second + decay^2 * third + ..."""
    if not signals_of_family:
        return 0.0
    points = sorted(
        (SEVERITY_POINTS.get(s.severity, 0) for s in signals_of_family),
        reverse=True,
    )
    total = 0.0
    for i, p in enumerate(points):
        total += p * (config.family_decay ** i)
    return total


def compute_score(signals: list[Signal], config: RulesConfig) -> int:
    by_family: dict[str, list[Signal]] = {}
    for s in signals:
        if s.status != "DETECTED":
            continue
        family = FAMILY_BY_SIGNAL.get(s.type, "textual")
        by_family.setdefault(family, []).append(s)

    total = 0.0
    for family, fam_signals in by_family.items():
        weight = config.family_weights.get(family, 10) / 40.0  # 40 = HIGH, база
        total += _family_points(fam_signals, config) * weight

    return min(MAX_SCORE, int(round(total)))


def compute_level(score: int, config: RulesConfig) -> str:
    if score <= config.level_low_max:
        return "LOW"
    if score <= config.level_medium_max:
        return "MEDIUM"
    if score <= config.level_high_max:
        return "HIGH"
    return "CRITICAL"


def compute_confidence(invoice: Invoice, history: VendorHistory, config: RulesConfig) -> str:
    """Уверенность в оценке: зависит от полноты данных, не от тяжести сигналов."""
    missing = 0
    if invoice.amount is None:
        missing += 1
    if invoice.currency is None:
        missing += 1
    if invoice.senderEmail is None:
        missing += 1
    if invoice.senderName is None:
        missing += 1
    if invoice.dueDate is None:
        missing += 1

    if not history.complete or missing >= 3 or len(history.priorInvoices) == 0:
        return "LOW"
    if missing <= 1 and len(history.priorInvoices) >= config.confidence_history_full_min:
        return "HIGH"
    return "MEDIUM"


def build_recommendations(signals: list[Signal]) -> list[str]:
    seen_types: set[str] = set()
    out: list[str] = []
    for s in signals:
        if s.status != "DETECTED":
            continue
        if s.type in seen_types:
            continue
        seen_types.add(s.type)
        text = RECOMMENDATION_BY_TYPE.get(s.type)
        if text:
            out.append(text)
    if not out:
        out.append("Явных признаков не обнаружено. Оплачивайте только через свои обычные проверенные каналы.")
    return out


def build_comparison(invoice: Invoice, history: VendorHistory) -> list[ComparisonRow]:
    if not history.priorInvoices:
        return []
    last = sorted(
        (h for h in history.priorInvoices if h.createdAt is not None),
        key=lambda h: h.createdAt, reverse=True,
    )
    if not last:
        return []
    prev = last[0]
    return [
        ComparisonRow(
            field="Supplier",
            current=invoice.senderName, previous=prev.senderName,
            differs=invoice.senderName != prev.senderName,
        ),
        ComparisonRow(
            field="PayPal email",
            current=invoice.senderEmail, previous=prev.senderEmail,
            differs=invoice.senderEmail != prev.senderEmail,
        ),
        ComparisonRow(
            field="Amount",
            current=f"{invoice.amount} {invoice.currency}" if invoice.amount is not None else None,
            previous=f"{prev.amount} {prev.currency}" if prev.amount is not None else None,
            differs=str(invoice.amount) != str(prev.amount),
        ),
    ]


def build_risk_result(
    invoice: Invoice, history: VendorHistory, config: RulesConfig, signals: list[Signal],
) -> RiskResult:
    score = compute_score(signals, config)
    level = compute_level(score, config)
    confidence = compute_confidence(invoice, history, config)
    return RiskResult(
        invoiceId=invoice.id,
        invoiceVersionHash=invoice.contentHash,
        riskScore=score,
        riskLevel=level,  # type: ignore[arg-type]
        confidence=confidence,  # type: ignore[arg-type]
        signals=signals,
        recommendations=build_recommendations(signals),
        comparison=build_comparison(invoice, history),
        engineVersion=config.version,
        analyzedAt=datetime.now(timezone.utc),
    )
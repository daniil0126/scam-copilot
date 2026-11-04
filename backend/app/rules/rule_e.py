from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .config import RulesConfig
from .types import Invoice, Signal, VendorHistory


RULE_VERSION_SUFFIX = "activity"
MIN_HISTORY_FOR_ACTIVITY = 3


def rule_e(invoice: Invoice, history: VendorHistory, config: RulesConfig) -> list[Signal]:
    rule_version = f"{RULE_VERSION_SUFFIX}-{config.version}"

    if not history.complete:
        return [Signal(
            type="UNUSUAL_SENDER_ACTIVITY", severity="LOW", status="INSUFFICIENT_DATA",
            evidence="История поставщика обрезана — оценка активности невозможна",
            evidenceData={"complete": False},
            source="RULE_ENGINE", ruleVersion=rule_version,
        )]

    if len(history.priorInvoices) < MIN_HISTORY_FOR_ACTIVITY:
        return [Signal(
            type="UNUSUAL_SENDER_ACTIVITY", severity="LOW", status="INSUFFICIENT_DATA",
            evidence=f"история {len(history.priorInvoices)} < {MIN_HISTORY_FOR_ACTIVITY}",
            evidenceData={"historyCount": len(history.priorInvoices),
                          "required": MIN_HISTORY_FOR_ACTIVITY},
            source="RULE_ENGINE", ruleVersion=rule_version,
        )]

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=config.activity_window_days)

    dated = [h for h in history.priorInvoices if h.createdAt is not None]
    if not dated:
        return [Signal(
            type="UNUSUAL_SENDER_ACTIVITY", severity="LOW", status="INSUFFICIENT_DATA",
            evidence="В истории нет дат создания инвойсов",
            evidenceData={}, source="RULE_ENGINE", ruleVersion=rule_version,
        )]

    def aware(dt: datetime) -> datetime:
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    in_window = [h for h in dated if aware(h.createdAt) >= window_start]
    observed = len(in_window)

    oldest = min(aware(h.createdAt) for h in dated)
    span_days = max(1, (now - oldest).days)
    expected = len(dated) * config.activity_window_days / span_days

    if expected <= 0:
        return []

    if observed <= expected * config.activity_burst_multiplier:
        return []

    return [Signal(
        type="UNUSUAL_SENDER_ACTIVITY", severity="MEDIUM", status="DETECTED",
        evidence=(f"{observed} инвойсов за {config.activity_window_days} дн. "
                  f"при ожидаемых ~{expected:.1f}"),
        evidenceData={
            "observed": observed,
            "expected": round(expected, 2),
            "windowDays": config.activity_window_days,
            "multiplier": config.activity_burst_multiplier,
            "spanDays": span_days,
        },
        source="RULE_ENGINE", ruleVersion=rule_version,
    )]
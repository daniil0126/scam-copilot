from __future__ import annotations

from .aggregator import build_risk_result
from .config import RulesConfig
from .rule_a import rule_a
from .rule_b import rule_b
from .rule_c import rule_c
from .rule_d import rule_d
from .rule_due import rule_due
from .rule_e import rule_e
from .rule_text import rule_text
from .types import Invoice, RiskResult, Signal, VendorHistory


def evaluate(invoice: Invoice, history: VendorHistory, config: RulesConfig) -> RiskResult:
    signals: list[Signal] = []
    signals.extend(rule_a(invoice, history, config))
    signals.extend(rule_b(invoice, history, config))
    signals.extend(rule_c(invoice, history, config))
    signals.extend(rule_d(invoice, history, config))
    signals.extend(rule_e(invoice, history, config))
    signals.extend(rule_text(invoice, history, config))
    signals.extend(rule_due(invoice, history, config))
    return build_risk_result(invoice, history, config, signals)
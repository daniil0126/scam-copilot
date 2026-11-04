from datetime import datetime, timezone
from decimal import Decimal

from app.rules.aggregator import (
    build_risk_result, compute_confidence, compute_level, compute_score,
)
from app.rules.config import RulesConfig
from app.rules.types import (
    HistoricalInvoice, Invoice, Signal, VendorHistory,
)

CFG = RulesConfig()


def _inv(**kw) -> Invoice:
    base = dict(id="INV-1", source="paypal_api", contentHash="h",
                amount=Decimal("100"), currency="USD",
                senderName="Acme", senderEmail="a@x.com")
    base.update(kw)
    return Invoice(**base)


def _sig(typ, sev, status="DETECTED", evidence="x") -> Signal:
    return Signal(type=typ, severity=sev, status=status, evidence=evidence,
                  evidenceData={}, source="RULE_ENGINE", ruleVersion="t-0")


def _hist(n=5, complete=True) -> VendorHistory:
    return VendorHistory(
        senderKey="x", complete=complete,
        priorInvoices=[HistoricalInvoice(id=f"h{i}", amount="100", currency="USD",
                                          createdAt=datetime(2026, 1, i + 1, tzinfo=timezone.utc))
                        for i in range(n)],
        totalCount=n,
    )


def test_no_signals_low():
    result = build_risk_result(_inv(), _hist(), CFG, [])
    assert result.riskScore == 0 and result.riskLevel == "LOW"


def test_single_high_signal():
    score = compute_score([_sig("SENDER_MISMATCH", "HIGH")], CFG)
    assert score > 0
    assert compute_level(score, CFG) in {"MEDIUM", "HIGH"}


def test_correlated_signals_decay():
    one = compute_score([_sig("DUPLICATE_EXACT", "HIGH")], CFG)
    two = compute_score([
        _sig("DUPLICATE_EXACT", "HIGH"),
        _sig("DUPLICATE_POTENTIAL", "HIGH"),
    ], CFG)
    # второй сигнал того же семейства даёт меньше, чем первый
    assert two < one * 2
    assert two > one


def test_score_capped_at_100():
    many = [_sig("SENDER_MISMATCH", "CRITICAL") for _ in range(20)]
    assert compute_score(many, CFG) <= 100


def test_insufficient_data_not_counted():
    with_data = compute_score([_sig("UNUSUAL_AMOUNT", "HIGH")], CFG)
    with_insufficient = compute_score([
        _sig("UNUSUAL_AMOUNT", "HIGH"),
        _sig("DUPLICATE_EXACT", "HIGH", status="INSUFFICIENT_DATA"),
    ], CFG)
    assert with_insufficient == with_data


def test_levels_thresholds():
    assert compute_level(0, CFG) == "LOW"
    assert compute_level(29, CFG) == "LOW"
    assert compute_level(30, CFG) == "MEDIUM"
    assert compute_level(59, CFG) == "MEDIUM"
    assert compute_level(60, CFG) == "HIGH"
    assert compute_level(79, CFG) == "HIGH"
    assert compute_level(80, CFG) == "CRITICAL"
    assert compute_level(100, CFG) == "CRITICAL"


def test_confidence_low_when_history_missing():
    c = compute_confidence(_inv(), VendorHistory(senderKey="x"), CFG)
    assert c == "LOW"


def test_confidence_low_when_incomplete():
    c = compute_confidence(_inv(), _hist(complete=False), CFG)
    assert c == "LOW"


def test_confidence_high_when_full_data():
    c = compute_confidence(_inv(), _hist(n=CFG.confidence_history_full_min + 2), CFG)
    assert c == "HIGH"


def test_confidence_low_when_many_fields_missing():
    inv = _inv(amount=None, currency=None, senderEmail=None, senderName=None)
    c = compute_confidence(inv, _hist(n=20), CFG)
    assert c == "LOW"


def test_recommendation_for_each_type():
    result = build_risk_result(
        _inv(), _hist(),
        CFG,
        [_sig("SENDER_MISMATCH", "HIGH"), _sig("SUSPICIOUS_LINK", "MEDIUM")],
    )
    assert len(result.recommendations) == 2
    assert all(isinstance(r, str) and r for r in result.recommendations)


def test_comparison_built():
    inv = _inv(amount=Decimal("200"))
    result = build_risk_result(inv, _hist(n=3), CFG, [])
    assert any(c.field == "Amount" and c.differs for c in result.comparison)


def test_engine_version_and_analyzed_at():
    result = build_risk_result(_inv(), _hist(), CFG, [])
    assert result.engineVersion == CFG.version
    assert result.analyzedAt is not None
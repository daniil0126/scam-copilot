from app.rules.clusters import build_clusters
from app.rules.types import Signal


def _dup(ref: str, typ: str = "DUPLICATE_EXACT") -> Signal:
    return Signal(type=typ, severity="HIGH", status="DETECTED",
                  evidence=f"ref {ref}", evidenceData={"refInvoiceId": ref},
                  source="RULE_ENGINE", ruleVersion="t-0")


def test_no_duplicates_no_clusters():
    assert build_clusters("A", []) == []


def test_single_pair_one_cluster():
    clusters = build_clusters("A", [_dup("B")])
    assert clusters == [["A", "B"]]


def test_transitive_merge():
    # A ~ B, B ~ C → один кластер [A, B, C]
    signals = [_dup("B"), _dup("C")]
    clusters = build_clusters("B", signals)
    assert clusters == [["B", "C"]]


def test_insufficient_data_ignored():
    s = Signal(type="DUPLICATE_EXACT", severity="LOW", status="INSUFFICIENT_DATA",
               evidence="no history", evidenceData={}, source="RULE_ENGINE", ruleVersion="t-0")
    assert build_clusters("A", [s]) == []


def test_non_duplicate_signals_ignored():
    s = Signal(type="UNUSUAL_AMOUNT", severity="HIGH", status="DETECTED",
               evidence="x", evidenceData={"refInvoiceId": "B"},
               source="RULE_ENGINE", ruleVersion="t-0")
    assert build_clusters("A", [s]) == []
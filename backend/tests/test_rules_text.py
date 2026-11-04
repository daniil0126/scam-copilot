from app.rules.config import RulesConfig
from app.rules.rule_text import rule_text
from app.rules.types import Invoice, VendorHistory

CFG = RulesConfig()
H = VendorHistory(senderKey="x")


def _inv(**kw) -> Invoice:
    base = dict(id="INV-1", source="paypal_api", contentHash="h")
    base.update(kw)
    return Invoice(**base)


def test_empty_note_no_signals():
    assert rule_text(_inv(note=None), H, CFG) == []
    assert rule_text(_inv(note=""), H, CFG) == []
    assert rule_text(_inv(note="   "), H, CFG) == []


def test_phone_detected():
    sigs = rule_text(_inv(note="call +1 555 0100 now"), H, CFG)
    assert any(s.type == "PHONE_IN_TEXT" for s in sigs)


def test_scam_wording():
    sigs = rule_text(_inv(note="Please call now about your subscription renewal"), H, CFG)
    assert any(s.type == "SCAM_WORDING" for s in sigs)


def test_brand_impersonation():
    sigs = rule_text(_inv(senderName="PayPal Support", senderEmail="help@evil.example", note=""), H, CFG)
    assert any(s.type == "BRAND_IMPERSONATION" for s in sigs)


def test_official_brand_ok():
    sigs = rule_text(_inv(senderName="PayPal", senderEmail="service@paypal.com", note=""), H, CFG)
    assert sigs == []


def test_phone_and_wording_together():
    sigs = rule_text(_inv(note="call +1 555 0100 now for refund"), H, CFG)
    types = {s.type for s in sigs}
    assert "PHONE_IN_TEXT" in types and "SCAM_WORDING" in types
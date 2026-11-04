from app.rules.config import RulesConfig
from app.rules.rule_d import rule_d
from app.rules.types import Invoice, VendorHistory

CFG = RulesConfig()
H = VendorHistory(senderKey="x")


def _inv(**kw) -> Invoice:
    base = dict(id="INV-1", source="paypal_api", contentHash="h")
    base.update(kw)
    return Invoice(**base)


def test_no_links_no_signals():
    assert rule_d(_inv(paymentLinks=None), H, CFG) == []
    assert rule_d(_inv(paymentLinks=[]), H, CFG) == []


def test_clean_paypal_no_signal():
    assert rule_d(_inv(paymentLinks=["https://www.paypal.com/invoice/p/#ABC"]), H, CFG) == []


def test_ip_host():
    sigs = rule_d(_inv(paymentLinks=["http://192.168.1.1/pay"]), H, CFG)
    assert len(sigs) == 1 and sigs[0].evidenceData["reason"] == "ip_host"


def test_punycode():
    sigs = rule_d(_inv(paymentLinks=["http://xn--pypal-4ve.com/pay"]), H, CFG)
    assert len(sigs) == 1 and sigs[0].evidenceData["reason"] == "punycode"


def test_deep_subdomain():
    sigs = rule_d(_inv(paymentLinks=["https://a.b.c.d.example.com/pay"]), H, CFG)
    assert len(sigs) == 1 and sigs[0].evidenceData["reason"] == "deep_subdomain"


def test_brand_foreign_domain():
    sigs = rule_d(_inv(paymentLinks=["https://paypal-secure.example/pay"]), H, CFG)
    assert len(sigs) == 1
    assert sigs[0].evidenceData["reason"] == "brand_foreign_domain"
    assert sigs[0].evidenceData["brand"] == "paypal"
    assert sigs[0].severity == "HIGH"


def test_official_subdomain_ok():
    assert rule_d(_inv(paymentLinks=["https://www.paypal.com/x"]), H, CFG) == []
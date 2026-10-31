from datetime import datetime, timezone
from decimal import Decimal

from app.rules.config import RulesConfig
from app.rules.relationships import find_relationships
from app.rules.types import ContactSnapshot, HistoricalInvoice, Invoice, VendorHistory

CFG = RulesConfig()


def _inv(**kw) -> Invoice:
    base = dict(id="INV-1", source="paypal_api", contentHash="h")
    base.update(kw)
    return Invoice(**base)


def _h(i: int, email: str, links=None, sig=None) -> HistoricalInvoice:
    return HistoricalInvoice(
        id=f"h{i}", amount="100", currency="USD",
        createdAt=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
        senderEmail=email, paymentLinks=links, itemsSignature=sig,
    )


def test_no_other_senders_no_relationships():
    h = VendorHistory(senderKey="a@x.com")
    assert find_relationships(_inv(senderEmail="a@x.com"), h) == []


def test_single_shared_link_is_observation():
    h = VendorHistory(senderKey="a@x.com", otherSenderInvoices=[
        _h(0, "b@y.com", links=["https://evil.example/pay"]),
    ])
    inv = _inv(senderEmail="a@x.com", paymentLinks=["https://evil.example/pay"])
    rels = find_relationships(inv, h)
    assert len(rels) == 1
    assert rels[0].kind == "observation"


def test_two_independent_matches_is_relationship():
    h = VendorHistory(senderKey="a@x.com", otherSenderInvoices=[
        _h(0, "b@y.com", links=["https://evil.example/pay"], sig="Widget|1|100.00"),
    ])
    inv = _inv(
        senderEmail="a@x.com",
        paymentLinks=["https://evil.example/pay"],
        senderPhone="+1 555 0100",
    )
    rels = find_relationships(inv, h, current_signature="Widget|1|100.00")
    assert len(rels) == 1
    assert rels[0].kind == "relationship"
    assert len(rels[0].sharedLinks) == 1
    assert len(rels[0].sharedSignatures) == 1


def test_self_not_included():
    h = VendorHistory(senderKey="a@x.com", otherSenderInvoices=[
        _h(0, "a@x.com", links=["https://x.example"]),
    ])
    inv = _inv(senderEmail="a@x.com", paymentLinks=["https://x.example"])
    assert find_relationships(inv, h) == []


def test_no_shared_features_no_relationship():
    h = VendorHistory(senderKey="a@x.com", otherSenderInvoices=[
        _h(0, "b@y.com", links=["https://other.example"]),
    ])
    inv = _inv(senderEmail="a@x.com", paymentLinks=["https://mine.example"])
    assert find_relationships(inv, h) == []


def test_min_independent_matches_from_config():
    assert RulesConfig().relationship_min_independent_matches == 2


def test_threshold_respected_from_config():
    cfg = RulesConfig(relationship_min_independent_matches=3)
    h = VendorHistory(senderKey="a@x.com", otherSenderInvoices=[
        _h(0, "b@y.com", links=["https://evil.example/pay"], sig="Widget|1|100.00"),
    ])
    inv = _inv(senderEmail="a@x.com", paymentLinks=["https://evil.example/pay"], senderPhone="+1 555 0100")
    rels = find_relationships(inv, h, current_signature="Widget|1|100.00", config=cfg)
    assert rels and rels[0].kind == "observation"  # 2 совпадения < порога 3
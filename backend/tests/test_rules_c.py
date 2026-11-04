from datetime import datetime, timezone
from app.rules.config import RulesConfig
from app.rules.rule_c import rule_c
from app.rules.types import Invoice, VendorHistory, HistoricalInvoice, ContactSnapshot

CFG = RulesConfig()


def _inv(**kw) -> Invoice:
    base = dict(id="INV-1", source="paypal_api", contentHash="h")
    base.update(kw)
    return Invoice(**base)


def _hist(emails, names=None, prior=1):
    names = names or [None] * len(emails)
    return VendorHistory(
        senderKey="x",
        priorInvoices=[HistoricalInvoice(id=f"h{i}", amount="100", currency="USD",
                                          createdAt=datetime(2026, 1, i + 1, tzinfo=timezone.utc))
                        for i in range(prior)],
        knownContacts=[ContactSnapshot(email=e, name=n) for e, n in zip(emails, names)],
        totalCount=prior, complete=True,
    )

def test_no_history_new_sender():
    sigs = rule_c(_inv(senderEmail="a@x.com"), VendorHistory(senderKey="x"), CFG)
    assert len(sigs) == 1
    assert sigs[0].type == "NEW_SENDER" and sigs[0].status == "DETECTED"
    # LOW on purpose: being a new sender is a fact, not a risk. Calibration relies on this: a MEDIUM-weight
    # signal would reach the MEDIUM band on its own and flag every first invoice (scenarios 1 and 7).
    assert sigs[0].severity == "LOW"


def test_email_changed_mismatch_high():
    h = _hist(["old@x.com"], ["Acme"])
    sigs = rule_c(_inv(senderEmail="evil@x.com", senderName="Acme"), h, CFG)
    assert any(s.type == "SENDER_MISMATCH" and s.severity == "HIGH" for s in sigs)


def test_same_email_same_name_no_signal():
    h = _hist(["a@x.com"], ["Acme"])
    sigs = rule_c(_inv(senderEmail="a@x.com", senderName="Acme"), h, CFG)
    assert not any(s.type in {"SENDER_MISMATCH", "SENDER_NAME_CHANGED", "NEW_SENDER"} for s in sigs)


def test_name_changed_same_email():
    h = _hist(["a@x.com"], ["Acme"])
    sigs = rule_c(_inv(senderEmail="a@x.com", senderName="Acme New Name"), h, CFG)
    assert any(s.type == "SENDER_NAME_CHANGED" for s in sigs)


def test_new_email_with_known_history_is_mismatch_not_new_sender():
    # в истории есть email, новый email → SENDER_MISMATCH (payee), не NEW_SENDER
    h = _hist(["a@x.com"], ["Acme"])
    sigs = rule_c(_inv(senderEmail="b@y.com", senderName="Different Co"), h, CFG)
    assert any(s.type == "SENDER_MISMATCH" for s in sigs)
    assert not any(s.type == "NEW_SENDER" for s in sigs)


def test_lookalike_domain_mismatch():
    h = _hist(["a@paypal.com"], ["PayPal"])
    sigs = rule_c(_inv(senderEmail="a@paypa1.com", senderName="PayPal"), h, CFG)
    assert any(s.type == "SENDER_MISMATCH" for s in sigs)

def test_email_mismatch_does_not_double_with_lookalike_domain():
    # email уже сменился → SENDER_MISMATCH по email; lookalike-домен не должен добавлять второй
    h = _hist(["a@paypa1.com"], ["PayPal"])
    sigs = rule_c(_inv(senderEmail="b@paypal.com", senderName="PayPal"), h, CFG)
    mismatches = [s for s in sigs if s.type == "SENDER_MISMATCH"]
    assert len(mismatches) == 1
    assert mismatches[0].evidenceData.get("currentEmail") == "b@paypal.com"
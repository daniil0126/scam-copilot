from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db import Base, SessionLocal, engine
from app.models import Check, InvoiceVersion
from app.normalize import Invoice
from app.vendor_history import build_vendor_history, items_signature, sender_key

ACCOUNT = "acct"
FIELDS = {"senderKey", "priorInvoices", "knownContacts", "otherSenderInvoices", "totalCount", "complete"}


@pytest.fixture
def db():
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        for table in (InvoiceVersion, Check):
            session.execute(delete(table))
        session.commit()
        yield session


def invoice(i="INV2-9", created="2026-10-09T00:00:00+00:00", email="a@acme.example.com", name="Acme", digest="h9"):
    return Invoice(id=i, source="paypal_api", senderEmail=email, senderName=name, contentHash=digest,
                   createdAt=datetime.fromisoformat(created))


def store(db, i, day, email="a@acme.example.com", name="Acme", digest=None, items=None, amount="10.00", phone=None):
    created = f"2026-10-{day:02d}T00:00:00Z"
    db.add(InvoiceVersion(
        account_id=ACCOUNT, invoice_id=i, content_hash=digest or f"{i}-h", raw={},
        normalized={"id": i, "createdAt": created, "senderEmail": email, "senderName": name, "senderPhone": phone,
                    "amount": amount, "currency": "USD", "invoiceNumber": i[-1], "items": items},
        seen_at=datetime(2026, 10, day),
    ))
    db.commit()


def test_shape_matches_contract(db):
    history = build_vendor_history(db, ACCOUNT, invoice())
    assert set(history) == FIELDS
    assert history["senderKey"] == "a@acme.example.com"
    assert history["priorInvoices"] == [] and history["knownContacts"] == [] and history["totalCount"] == 0
    assert history["complete"] is True


def test_only_earlier_invoices_of_the_same_sender_oldest_first(db):
    store(db, "INV2-3", 3)
    store(db, "INV2-1", 1)
    store(db, "INV2-12", 12)  # created after the evaluated invoice: not history
    store(db, "INV2-5", 5, email="b@other.example.com", name="Other")
    history = build_vendor_history(db, ACCOUNT, invoice())
    assert [h["id"] for h in history["priorInvoices"]] == ["INV2-1", "INV2-3"]
    assert [h["id"] for h in history["otherSenderInvoices"]] == ["INV2-5"]
    assert history["totalCount"] == 2


def test_evaluated_invoice_is_not_its_own_history_but_its_earlier_versions_are_contacts(db):
    store(db, "INV2-9", 4, email="old@acme.example.com", digest="old")
    store(db, "INV2-9", 9, email="a@acme.example.com", digest="h9")
    history = build_vendor_history(db, ACCOUNT, invoice())
    assert history["priorInvoices"] == []
    assert [c["email"] for c in history["knownContacts"]] == ["old@acme.example.com"]


def test_known_contacts_are_distinct_with_first_and_last_seen(db):
    store(db, "INV2-1", 1)
    store(db, "INV2-2", 2)
    store(db, "INV2-3", 3, email="a@acme.example.com", phone="+1 555")
    contacts = build_vendor_history(db, ACCOUNT, invoice())["knownContacts"]
    assert len(contacts) == 2
    first = contacts[0]
    assert first["firstSeen"] == datetime(2026, 10, 1, tzinfo=timezone.utc)
    assert first["lastSeen"] == datetime(2026, 10, 2, tzinfo=timezone.utc)


def test_payer_side_checks_count_as_history(db):
    db.add(Check(id="c1", paypal_invoice_id="INV2-7", supplier_name="Acme", supplier_email="A@Acme.example.com",
                 number="7", amount=12.5, currency="USD", checked_at=datetime(2026, 10, 7), result={}))
    db.commit()
    history = build_vendor_history(db, ACCOUNT, invoice())
    assert [(h["id"], h["amount"]) for h in history["priorInvoices"]] == [("INV2-7", "12.5")]


def test_same_input_gives_the_same_history(db):
    store(db, "INV2-1", 1)
    store(db, "INV2-2", 2)
    assert build_vendor_history(db, ACCOUNT, invoice()) == build_vendor_history(db, ACCOUNT, invoice())


def test_history_is_cut_and_marked_incomplete(db, monkeypatch):
    import app.vendor_history as vh
    monkeypatch.setattr(vh, "MAX_PRIOR", 2)
    for n in range(1, 5):
        store(db, f"INV2-{n}", n)
    history = build_vendor_history(db, ACCOUNT, invoice())
    assert [h["id"] for h in history["priorInvoices"]] == ["INV2-3", "INV2-4"]  # the newest two, oldest first
    assert history["totalCount"] == 4 and history["complete"] is False


def test_no_account_and_no_sender(db):
    history = build_vendor_history(db, None, invoice(email=None, name=None))
    assert history["senderKey"] == "" and history["priorInvoices"] == []


def test_helpers():
    assert sender_key("  A@Acme.Example.com ", "x") == "a@acme.example.com"
    assert sender_key(None, " Acme   Ltd ") == "acme ltd"
    assert sender_key(None, None) == ""
    assert items_signature(None) is None
    one = items_signature([{"name": "Work ", "quantity": "1"}])
    assert one == items_signature([{"name": "work", "quantity": "1"}]) != items_signature([{"name": "work", "quantity": "2"}])

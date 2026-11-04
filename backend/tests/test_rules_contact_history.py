from datetime import datetime, timezone

from app.rules.contact_history import extract_contact_changes
from app.rules.types import ContactSnapshot, HistoricalInvoice, VendorHistory


def _dt(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=timezone.utc)


def _h(i: int, day: int, email: str | None = None, name: str | None = None) -> HistoricalInvoice:
    return HistoricalInvoice(id=f"h{i}", amount="100", currency="USD",
                             createdAt=_dt(day), senderEmail=email, senderName=name)


def test_no_history_no_changes():
    assert extract_contact_changes(VendorHistory(senderKey="x")) == []


def test_email_change_detected():
    h = VendorHistory(
        senderKey="x",
        priorInvoices=[
            _h(0, 1, email="old@x.com", name="Acme"),
            _h(1, 2, email="new@x.com", name="Acme"),
        ],
    )
    changes = extract_contact_changes(h)
    assert any(c.field == "email" and c.old == "old@x.com" and c.new == "new@x.com" for c in changes)


def test_name_change_detected():
    h = VendorHistory(
        senderKey="x",
        priorInvoices=[
            _h(0, 1, email="a@x.com", name="Old Name"),
            _h(1, 2, email="a@x.com", name="New Name"),
        ],
    )
    changes = extract_contact_changes(h)
    assert any(c.field == "name" and c.old == "Old Name" and c.new == "New Name" for c in changes)


def test_no_changes_when_stable():
    h = VendorHistory(
        senderKey="x",
        priorInvoices=[
            _h(0, 1, email="a@x.com", name="Acme"),
            _h(1, 2, email="a@x.com", name="Acme"),
        ],
    )
    assert extract_contact_changes(h) == []


def test_known_contacts_and_invoices_merged():
    h = VendorHistory(
        senderKey="x",
        priorInvoices=[_h(0, 5, email="b@x.com", name="Acme")],
        knownContacts=[
            ContactSnapshot(email="a@x.com", name="Acme", firstSeen=_dt(1)),
            ContactSnapshot(email="b@x.com", name="Acme", firstSeen=_dt(5)),
        ],
    )
    changes = extract_contact_changes(h)
    assert any(c.field == "email" for c in changes)
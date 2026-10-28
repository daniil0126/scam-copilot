from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import app.checks as checks
from app.db import Base, engine
from app.main import app

DUE = (date.today() + timedelta(days=14)).isoformat()
INVOICES: dict = {}


def make(name="Acme Supplies Ltd.", email="billing@acme.example.com", amount=100.0):
    return {"number": "1", "supplier": {"name": name, "email": email, "phone": ""}, "amount": amount,
            "currency": "USD", "dueDate": DUE, "note": "", "status": "SENT"}


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    INVOICES.clear()

    async def fake_get_invoice(invoice_id):
        return INVOICES[invoice_id]

    monkeypatch.setattr(checks, "get_invoice", fake_get_invoice)


client = TestClient(app)


def check(invoice_id):
    return client.post("/checks", json={"invoice_id": invoice_id}).json()


def test_rechecking_same_invoice_does_not_duplicate():
    INVOICES["INV2-A"] = make()
    first = check("INV2-A")
    second = check("INV2-A")
    assert first["id"] == second["id"]
    assert len(client.get("/checks").json()) == 1


def test_recheck_is_not_compared_with_itself():
    INVOICES["INV2-A"] = make()
    assert check("INV2-A")["findings"][0]["label"] == "New supplier"
    assert check("INV2-A")["findings"][0]["label"] == "New supplier"  # not "Supplier confirmed"


def test_recheck_picks_up_changes_to_the_invoice():
    INVOICES["INV2-A"] = make(amount=100)
    check("INV2-A")
    INVOICES["INV2-A"] = make(amount=250)
    check("INV2-A")
    entries = client.get("/checks").json()
    assert len(entries) == 1 and entries[0]["invoice"]["amount"] == 250


def test_different_invoices_are_separate_entries_and_compare():
    INVOICES["INV2-A"], INVOICES["INV2-B"] = make(), make(amount=110)
    check("INV2-A")
    second = check("INV2-B")
    assert len(client.get("/checks").json()) == 2
    assert second["level"] == "low" and second["score"] == 0

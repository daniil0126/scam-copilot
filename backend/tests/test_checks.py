from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import app.checks as checks
from app.db import Base, engine
from app.main import app

DUE = (date.today() + timedelta(days=14)).isoformat()
INVOICES: dict = {}
created: dict = {}  # invoice id -> create_time, used by the fake list


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

    async def fake_fetch_invoices(limit=500):
        entries = [{"id": i, "createdAt": created.get(i, ""), "invoice": inv} for i, inv in INVOICES.items()]
        return {"invoices": entries, "total": len(entries), "truncated": False}

    monkeypatch.setattr(checks, "get_invoice", fake_get_invoice)
    monkeypatch.setattr(checks, "fetch_invoices", fake_fetch_invoices)
    created.clear()


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


def bulk():
    return client.post("/checks/bulk").json()


def test_bulk_with_no_invoices():
    body = bulk()
    assert body["results"] == [] and body["errors"] == []
    assert body["summary"] == {"low": 0, "medium": 0, "high": 0, "total": 0, "failed": 0}


def test_bulk_processes_oldest_first_and_summarises():
    # Listed newest first (as PayPal does); the 4.5x invoice is older, so it must be the baseline.
    INVOICES["INV2-NEW"], INVOICES["INV2-OLD"] = make(amount=500), make(amount=100)
    created.update({"INV2-NEW": "2025-02-01T00:00:00Z", "INV2-OLD": "2025-01-01T00:00:00Z"})
    body = bulk()
    assert [r["invoice"]["amount"] for r in body["results"]] == [100, 500]
    assert body["results"][0]["findings"][0]["label"] == "New supplier"
    assert body["results"][1]["level"] == "medium"  # 5x the previous amount
    assert body["summary"] == {"low": 1, "medium": 1, "high": 0, "total": 2, "failed": 0}


def test_bulk_rerun_is_stable_and_does_not_duplicate():
    for i, amount in enumerate((100, 110, 500)):
        INVOICES[f"INV2-{i}"] = make(amount=amount)
        created[f"INV2-{i}"] = f"2025-01-0{i + 1}T00:00:00Z"
    first, second = bulk(), bulk()
    assert [r["level"] for r in first["results"]] == [r["level"] for r in second["results"]]
    assert [r["id"] for r in first["results"]] == [r["id"] for r in second["results"]]
    assert len(client.get("/checks").json()) == 3


def test_bulk_one_broken_invoice_does_not_stop_the_rest():
    INVOICES["INV2-A"], INVOICES["INV2-BAD"], INVOICES["INV2-C"] = make(), {"number": "1"}, make(amount=105)
    created.update({"INV2-A": "2025-01-01", "INV2-BAD": "2025-01-02", "INV2-C": "2025-01-03"})
    body = bulk()
    assert body["summary"]["total"] == 2 and body["summary"]["failed"] == 1
    assert body["errors"][0]["invoiceId"] == "INV2-BAD"
    assert len(client.get("/checks").json()) == 2

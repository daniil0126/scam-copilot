import pytest
from fastapi.testclient import TestClient

import app.paypal as paypal
from app.main import app

client = TestClient(app)


def raw(i):
    return {"id": f"INV2-{i}", "status": "SENT", "detail": {"invoice_number": str(i), "currency_code": "USD",
            "metadata": {"create_time": f"2025-01-{i % 28 + 1:02d}T00:00:00Z"}, "payment_term": {"due_date": "2030-01-01"}},
            "invoicer": {"business_name": "Acme", "email_address": "a@acme.example.com"},
            "amount": {"currency_code": "USD", "value": "10.00"}}


@pytest.fixture
def pages(monkeypatch):
    calls = []

    def serve(total):
        async def fake_request(method, path, json=None, client=None):
            calls.append(path)
            page = int(path.split("page=")[1].split("&")[0])
            ids = range((page - 1) * 100, min(page * 100, total))
            return {"total_items": total, "total_pages": max(1, -(-total // 100)), "items": [raw(i) for i in ids]}
        monkeypatch.setattr(paypal, "paypal_request", fake_request)
        return calls

    return serve


def test_empty_account(pages):
    pages(0)
    assert client.get("/paypal/invoices").json() == {"invoices": [], "total": 0, "truncated": False}


def test_walks_all_pages(pages):
    calls = pages(250)
    body = client.get("/paypal/invoices").json()
    assert len(body["invoices"]) == 250 and len(calls) == 3
    first = body["invoices"][0]
    assert first["id"] == "INV2-0" and first["invoice"]["supplier"]["name"] == "Acme" and first["invoice"]["amount"] == 10.0


def test_stops_at_the_limit(pages):
    calls = pages(900)
    body = client.get("/paypal/invoices").json()
    assert len(body["invoices"]) == 500 and body["truncated"] and body["total"] == 900 and len(calls) == 5


def test_loads_details_for_items_without_supplier_name(monkeypatch):
    nameless = raw(1)
    nameless["invoicer"] = {"email_address": "a@acme.example.com"}

    async def fake_request(method, path, json=None, client=None):
        if "page=" in path:
            return {"total_items": 1, "total_pages": 1, "items": [nameless]}
        return raw(1)  # the single-invoice response has the name

    monkeypatch.setattr(paypal, "paypal_request", fake_request)
    assert client.get("/paypal/invoices").json()["invoices"][0]["invoice"]["supplier"]["name"] == "Acme"

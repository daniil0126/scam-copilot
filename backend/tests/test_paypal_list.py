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


def test_date_window_uses_search_with_rfc3339_range(monkeypatch):
    from datetime import datetime, timezone
    seen = []

    async def fake_request(method, path, json=None, client=None):
        seen.append((method, path.split("?")[0], json))
        return {"total_items": 1, "total_pages": 1, "items": [raw(1)]}
    monkeypatch.setattr(paypal, "paypal_request", fake_request)
    import asyncio
    out = asyncio.run(paypal.fetch_invoices(created_from=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)))
    assert seen == [("POST", "/v2/invoicing/search-invoices", {"creation_date_range": {"start": "2026-01-02T03:04:05Z"}})]
    assert len(out["invoices"]) == 1


@pytest.mark.parametrize("status,expected", [(401, 401), (403, 403), (429, 429), (500, 502)])
def test_paypal_errors_keep_their_meaning(monkeypatch, status, expected):
    import asyncio, httpx
    from fastapi import HTTPException

    class FakeClient:
        async def request(self, *a, **k):
            return httpx.Response(status, text="x")

    async def token(_):
        return "t"
    async def no_wait(_):
        pass
    monkeypatch.setattr(paypal, "get_access_token", token)
    monkeypatch.setattr(paypal.asyncio, "sleep", no_wait)
    with pytest.raises(HTTPException) as e:
        asyncio.run(paypal.paypal_request("GET", "/x", client=FakeClient()))
    assert e.value.status_code == expected


def _scripted(monkeypatch, statuses, headers=None):
    import httpx
    sleeps, calls = [], []

    class FakeClient:
        async def request(self, method, *a, **k):
            calls.append(method)
            status = statuses[min(len(calls) - 1, len(statuses) - 1)]
            return httpx.Response(status, json={"ok": True} if status == 200 else {}, headers=headers or {})

    async def token(_):
        return "t"

    async def fake_sleep(seconds):
        sleeps.append(seconds)
    monkeypatch.setattr(paypal, "get_access_token", token)
    monkeypatch.setattr(paypal.asyncio, "sleep", fake_sleep)
    return FakeClient(), calls, sleeps


def test_429_waits_for_retry_after_then_succeeds(monkeypatch):
    import asyncio
    client_, calls, sleeps = _scripted(monkeypatch, [429, 200], {"Retry-After": "2"})
    assert asyncio.run(paypal.paypal_request("GET", "/x", client=client_)) == {"ok": True}
    assert len(calls) == 2 and sleeps == [2.0]


def test_retry_after_is_capped(monkeypatch):
    import asyncio
    client_, _, sleeps = _scripted(monkeypatch, [429, 200], {"Retry-After": "600"})
    asyncio.run(paypal.paypal_request("GET", "/x", client=client_))
    assert sleeps == [paypal.MAX_WAIT]


def test_5xx_on_a_read_is_retried_and_gives_up_after_three_attempts(monkeypatch):
    import asyncio
    from fastapi import HTTPException
    client_, calls, sleeps = _scripted(monkeypatch, [503])
    with pytest.raises(HTTPException) as e:
        asyncio.run(paypal.paypal_request("GET", "/x", client=client_))
    assert e.value.status_code == 502 and len(calls) == 3 and len(sleeps) == 2 and sleeps[1] > sleeps[0] * 0.9


def test_5xx_on_a_write_is_not_retried(monkeypatch):
    import asyncio
    from fastapi import HTTPException
    client_, calls, _ = _scripted(monkeypatch, [503, 200])
    with pytest.raises(HTTPException):
        asyncio.run(paypal.paypal_request("POST", "/v2/invoicing/invoices", json={}, client=client_))
    assert len(calls) == 1


def test_search_post_counts_as_a_read(monkeypatch):
    import asyncio
    client_, calls, _ = _scripted(monkeypatch, [503, 200])
    asyncio.run(paypal.paypal_request("POST", "/v2/invoicing/search-invoices?page=1", json={}, client=client_))
    assert len(calls) == 2

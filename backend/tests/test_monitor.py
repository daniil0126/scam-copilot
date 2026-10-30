import asyncio
from copy import deepcopy

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

import app.monitor as monitor
import app.paypal as paypal
from app.db import SessionLocal
from app.main import app
from app.models import Check, InvoiceVersion, MonitoredInvoice, SyncState

client = TestClient(app)


def full(i, status="SENT", value="10.00"):
    """An invoice as `GET /v2/invoicing/invoices/{id}` returns it."""
    return {"id": f"INV2-{i}", "status": status, "detail": {"invoice_number": str(i), "currency_code": "USD",
            "invoice_date": "2026-10-01", "metadata": {"create_time": f"2026-10-{i + 1:02d}T00:00:00Z",
            "last_update_time": "2026-10-20T00:00:00Z"}, "payment_term": {"due_date": "2030-01-01"}},
            "invoicer": {"business_name": "Acme", "email_address": "a@acme.example.com"},
            "primary_recipients": [{"billing_info": {"email_address": "me@example.com"}}],
            "items": [{"name": "Work", "quantity": "1", "unit_amount": {"value": value}}],
            "amount": {"currency_code": "USD", "value": value}}


def as_list_item(invoice):
    """List items have no `items` and no `last_update_time`."""
    item = deepcopy(invoice)
    item.pop("items")
    item["detail"]["metadata"].pop("last_update_time")
    return item


class World:
    def __init__(self):
        self.invoices = {}
        self.list_error = None
        self.detail_errors = set()
        self.list_calls = []
        self.detail_calls = []


@pytest.fixture
def world(monkeypatch):
    w = World()

    async def fake_request(method, path, json=None, client=None):
        if path.startswith("/v2/invoicing/search-invoices"):
            w.list_calls.append(json["creation_date_range"])
            if w.list_error:
                raise w.list_error
            items = [as_list_item(i) for i in w.invoices.values()]
            return {"total_items": len(items), "total_pages": 1, "items": items}
        invoice_id = path.rsplit("/", 1)[1]
        w.detail_calls.append(invoice_id)
        if invoice_id in w.detail_errors:
            raise HTTPException(502, "PayPal error 500")
        return deepcopy(w.invoices[invoice_id])

    monkeypatch.setattr(paypal, "paypal_request", fake_request)
    with SessionLocal() as db:
        for table in (InvoiceVersion, MonitoredInvoice, SyncState, Check):
            db.execute(delete(table))
        db.commit()
    return w


def sync():
    async def run():
        with SessionLocal() as db:
            return await monitor.sync_once(db)
    return asyncio.run(run())


def count(model):
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(model))


def state():
    with SessionLocal() as db:
        return db.get(SyncState, monitor.account_id())


def test_new_invoice_is_handled_once(world):
    world.invoices["INV2-1"] = full(1)
    assert sync() == {"skipped": False, "new": 1, "failed": 0}
    assert (count(MonitoredInvoice), count(InvoiceVersion), count(Check)) == (1, 1, 1)
    assert state().state == "ACTIVE" and state().last_successful_sync_at is not None
    with SessionLocal() as db:
        version = db.scalars(select(InvoiceVersion)).one()
        assert version.account_id == monitor.account_id() and version.raw["id"] == "INV2-1"
        assert version.normalized["senderName"] == "Acme"


def test_second_pass_adds_nothing_and_asks_no_details(world):
    world.invoices["INV2-1"] = full(1)
    sync()
    assert sync() == {"skipped": False, "new": 0, "failed": 0}
    assert (count(MonitoredInvoice), count(InvoiceVersion), count(Check)) == (1, 1, 1)
    assert world.detail_calls == ["INV2-1"]  # the unchanged list item needed no detail request


def test_changed_invoice_gets_a_new_version(world):
    world.invoices["INV2-1"] = full(1)
    sync()
    world.invoices["INV2-1"] = full(1, status="PAID")
    assert sync()["new"] == 1
    assert (count(MonitoredInvoice), count(InvoiceVersion), count(Check)) == (1, 2, 1)  # the check entry is updated
    with SessionLocal() as db:
        current = db.scalars(select(MonitoredInvoice)).one().current_version_hash
        assert db.scalars(select(InvoiceVersion).where(InvoiceVersion.content_hash == current)).one().normalized["status"] == "PAID"


def test_timestamp_alone_is_not_a_new_version(world):
    world.invoices["INV2-1"] = full(1)
    sync()
    world.invoices["INV2-1"]["detail"]["metadata"]["last_update_time"] = "2026-10-29T00:00:00Z"
    world.invoices["INV2-1"]["status"] = "SENT"
    sync()
    assert count(InvoiceVersion) == 1


def test_returning_to_an_old_version_reuses_it(world):
    world.invoices["INV2-1"] = full(1)
    sync()
    world.invoices["INV2-1"] = full(1, status="PAID")
    sync()
    world.invoices["INV2-1"] = full(1)
    assert sync()["new"] == 0
    assert count(InvoiceVersion) == 2
    with SessionLocal() as db:
        current = db.scalars(select(MonitoredInvoice)).one().current_version_hash
        assert db.scalars(select(InvoiceVersion).where(InvoiceVersion.content_hash == current)).one().normalized["status"] == "SENT"


def test_listing_error_does_not_crash_and_keeps_the_checkpoint(world):
    world.invoices["INV2-1"] = full(1)
    sync()
    before = state().last_successful_sync_at
    world.list_error = HTTPException(429, "PayPal rate limit reached, try again later")
    assert sync()["failed"] == 1
    assert state().state == "ERROR" and "rate limit" in state().last_error
    assert state().last_successful_sync_at == before
    world.list_error = None
    sync()
    assert state().state == "ACTIVE" and state().last_error is None


def test_one_broken_invoice_does_not_stop_the_rest_and_holds_the_checkpoint(world):
    world.invoices["INV2-1"] = full(1)
    world.invoices["INV2-2"] = full(2)
    world.invoices["INV2-3"] = full(3)
    world.detail_errors = {"INV2-2"}
    assert sync() == {"skipped": False, "new": 2, "failed": 1}
    assert count(InvoiceVersion) == 2
    assert state().state == "ERROR" and "INV2-2" in state().last_error and state().last_successful_sync_at is None

    world.detail_errors = set()
    assert sync() == {"skipped": False, "new": 1, "failed": 0}  # only the failed one is redone
    assert count(InvoiceVersion) == 3 and state().state == "ACTIVE" and state().last_successful_sync_at is not None


def test_failed_check_leaves_the_version_unseen_so_the_next_pass_retries(world, monkeypatch):
    world.invoices["INV2-1"] = full(1)
    working = monitor.run_check

    async def broken(*a, **k):
        raise RuntimeError("scoring failed")
    monkeypatch.setattr(monitor, "run_check", broken)
    assert sync()["failed"] == 1 and count(InvoiceVersion) == 0 and count(MonitoredInvoice) == 0
    monkeypatch.setattr(monitor, "run_check", working)
    assert sync()["new"] == 1 and count(InvoiceVersion) == 1 and count(Check) == 1


def test_pause_stops_polling_and_resume_restarts_it(world):
    world.invoices["INV2-1"] = full(1)
    assert client.post("/monitoring/pause").json() == {"state": "PAUSED"}
    assert sync() == {"skipped": True, "new": 0, "failed": 0}
    assert world.list_calls == [] and count(InvoiceVersion) == 0
    assert client.post("/monitoring/sync").status_code == 409
    assert client.post("/monitoring/resume").json() == {"state": "ACTIVE"}
    assert sync()["new"] == 1


def test_pause_during_a_pass_is_not_overwritten(world, monkeypatch):
    world.invoices["INV2-1"] = full(1)
    original = paypal.paypal_request

    async def pausing(method, path, json=None, client=None):
        if not path.startswith("/v2/invoicing/search-invoices"):
            client_.post("/monitoring/pause")
        return await original(method, path, json, client)
    client_ = client
    monkeypatch.setattr(paypal, "paypal_request", pausing)
    sync()
    assert state().state == "PAUSED"


def test_pause_stops_the_pass_before_the_next_invoice(world, monkeypatch):
    for i in (1, 2, 3):
        world.invoices[f"INV2-{i}"] = full(i)
    original = paypal.paypal_request

    async def pausing(method, path, json=None, client=None):
        if not path.startswith("/v2/invoicing/search-invoices"):
            client_.post("/monitoring/pause")
        return await original(method, path, json, client)
    client_ = client
    monkeypatch.setattr(paypal, "paypal_request", pausing)
    assert sync()["skipped"] is True
    assert count(InvoiceVersion) == 1  # the invoice in flight is finished, nothing after it
    assert state().state == "PAUSED" and state().last_successful_sync_at is None
    assert world.detail_calls == ["INV2-1"]


def test_every_pass_re_reads_the_lookback_window(world):
    from datetime import datetime, timedelta

    def parse(value):
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    sync()
    sync()
    for window in world.list_calls:
        assert abs((parse(window["end"]) - parse(window["start"])) - monitor.LOOKBACK) < timedelta(seconds=5)


def test_monitoring_endpoint_shape(world):
    world.invoices["INV2-1"] = full(1)
    sync()
    body = client.get("/monitoring").json()
    assert set(body) == {"state", "lastSuccessfulSyncAt", "totalInvoices", "highRisk", "criticalRisk",
                         "potentialDuplicates", "vendorAnomalies", "recentEvents", "errors"}
    assert body["state"] == "ACTIVE" and body["totalInvoices"] == 1 and body["lastSuccessfulSyncAt"].endswith("Z")
    assert body["errors"] == []


def test_recent_events_describe_the_arrived_invoice(world):
    world.invoices["INV2-1"] = full(1)
    sync()
    world.invoices["INV2-1"] = full(1, status="PAID")
    sync()
    events = client.get("/monitoring").json()["recentEvents"]
    assert [e["eventType"] for e in events] == ["INVOICE_UPDATED", "NEW_INVOICE"]
    new = events[1]
    assert (new["invoiceId"], new["invoiceNumber"], new["senderName"], new["amount"], new["currency"], new["status"]) == (
        "INV2-1", "1", "Acme", "10.00", "USD", "SENT")
    assert new["riskLevel"] in ("low", "medium", "high") and isinstance(new["signals"], list)
    assert new["detectedAt"].endswith("Z") and events[0]["status"] == "PAID"


def test_monitoring_endpoint_before_any_pass(world):
    body = client.get("/monitoring").json()
    assert body["state"] == "ACTIVE" and body["lastSuccessfulSyncAt"] is None and body["totalInvoices"] == 0


def test_loop_keeps_going_after_a_crashed_pass(monkeypatch):
    runs = []

    async def flaky(db):
        runs.append(1)
        if len(runs) == 1:
            raise RuntimeError("boom")
        return {}
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 3:
            raise asyncio.CancelledError
    monkeypatch.setattr(monitor, "sync_once", flaky)
    monkeypatch.setattr(monitor.asyncio, "sleep", fake_sleep)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(monitor._loop())
    assert len(runs) == 3 and sleeps == [monitor.INTERVAL] * 3


def test_account_id_is_a_short_hash_that_hides_the_client_id(monkeypatch):
    monkeypatch.setattr(paypal, "PAYPAL_CLIENT_ID", "client-id-123")
    first = monitor.account_id()
    assert first == monitor.account_id() and first.startswith("acc_") and len(first) == 12
    assert "client-id-123" not in first
    monkeypatch.setattr(paypal, "PAYPAL_CLIENT_ID", "other")
    assert monitor.account_id() != first

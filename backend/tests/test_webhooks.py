import asyncio
import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

import app.monitor as monitor
import app.paypal as paypal
import app.webhooks as webhooks
from app.db import SessionLocal
from app.main import app
from app.models import Check, InvoiceVersion, MonitoredInvoice, SyncState
from tests.test_monitor import full

client = TestClient(app)
EVENT = json.loads((Path(__file__).parent / "fixtures/paypal/webhook_invoice_created.json").read_text())
INVOICE_ID = EVENT["resource"]["invoice"]["id"]
HEADERS = {
    "paypal-auth-algo": "SHA256withRSA", "paypal-cert-url": "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-1",
    "paypal-transmission-id": "t-1", "paypal-transmission-sig": "sig", "paypal-transmission-time": "2026-10-31T10:13:37Z",
}


class PayPal:
    def __init__(self):
        self.verdict = "SUCCESS"
        self.calls = []
        self.invoice = full(1)
        self.invoice["id"] = INVOICE_ID


@pytest.fixture
def world(monkeypatch):
    w = PayPal()

    async def fake_request(method, path, json=None, client=None):
        w.calls.append((method, path, json))
        if path == "/v1/notifications/verify-webhook-signature":
            return {"verification_status": w.verdict}
        if path == f"/v2/invoicing/invoices/{INVOICE_ID}":
            return deepcopy(w.invoice)
        raise HTTPException(404, "Invoice not found in PayPal")

    handled = []

    async def fake_handle(invoice_id, event_type):
        handled.append(invoice_id)

    monkeypatch.setattr(paypal, "paypal_request", fake_request)
    monkeypatch.setattr(webhooks, "handle", fake_handle)  # the route test only needs to know it was started
    monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-ID")
    w.handled = handled
    with SessionLocal() as db:
        for table in (InvoiceVersion, MonitoredInvoice, SyncState, Check):
            db.execute(delete(table))
        db.commit()
    return w


def post(event=EVENT, headers=HEADERS):
    return client.post("/webhooks/paypal", json=event, headers=headers)


def count(model):
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(model))


def test_off_without_a_webhook_id(world, monkeypatch):
    monkeypatch.delenv("PAYPAL_WEBHOOK_ID")
    assert post().status_code == 503 and not world.calls


def test_an_event_that_does_not_verify_is_dropped(world):
    world.verdict = "FAILURE"
    r = post()
    assert r.status_code == 401 and not world.handled


def test_missing_signature_headers_are_refused_without_asking_paypal(world):
    r = post(headers={})
    assert r.status_code == 401 and not world.calls and not world.handled


def test_the_signature_is_checked_with_the_event_and_the_webhook_id(world):
    post()
    method, path, body = world.calls[0]
    assert (method, path) == ("POST", "/v1/notifications/verify-webhook-signature")
    assert body["webhook_id"] == "WH-ID" and body["webhook_event"] == EVENT and body["transmission_id"] == "t-1"


def test_a_verified_invoice_event_starts_the_handler_with_the_invoice_id_only(world):
    r = post()
    assert r.status_code == 200 and r.json() == {"accepted": True, "invoiceId": INVOICE_ID}
    assert world.handled == [INVOICE_ID]


@pytest.mark.parametrize("change", [
    lambda e: e.update(event_type="PAYMENT.SALE.COMPLETED"),
    lambda e: e["resource"]["invoice"].update(id="../../v1/oauth2/token"),
    lambda e: e["resource"]["invoice"].update(id="INV2-1?x=1"),
    lambda e: e["resource"].pop("invoice"),
    lambda e: e.update(resource="invoice"),
])
def test_other_events_and_unsafe_ids_are_acknowledged_but_not_acted_on(world, change):
    event = deepcopy(EVENT)
    change(event)
    r = post(event)
    assert r.status_code == 200 and r.json()["accepted"] is False and not world.handled


def test_a_body_that_is_not_an_event_is_refused(world):
    assert client.post("/webhooks/paypal", content=b"not json", headers=HEADERS).status_code == 400
    assert client.post("/webhooks/paypal", json=[1, 2], headers=HEADERS).status_code == 400


# The handler itself, with the real function and a fake PayPal.
@pytest.fixture
def handler(monkeypatch):
    w = PayPal()
    calls = []

    async def fake_request(method, path, json=None, client=None):
        calls.append(path)
        return deepcopy(w.invoice)

    monkeypatch.setattr(paypal, "paypal_request", fake_request)
    with SessionLocal() as db:
        for table in (InvoiceVersion, MonitoredInvoice, SyncState, Check):
            db.execute(delete(table))
        db.commit()
    w.calls = calls
    return w


def handle():
    asyncio.run(webhooks.handle(INVOICE_ID, "INVOICING.INVOICE.UPDATED"))


def test_the_invoice_is_read_from_paypal_not_taken_from_the_event(handler):
    handler.invoice["amount"]["value"] = "12.00"  # what PayPal says now, whatever the event body carried
    handle()
    with SessionLocal() as db:
        version = db.scalars(select(InvoiceVersion)).one()
    assert version.normalized["amount"] == "12.00" and handler.calls == [f"/v2/invoicing/invoices/{INVOICE_ID}"]
    assert (count(MonitoredInvoice), count(Check)) == (1, 1)


def test_events_in_a_batch_for_one_version_store_it_once(handler):
    handle()
    handle()
    handle()
    assert (count(InvoiceVersion), count(Check), count(MonitoredInvoice)) == (1, 1, 1)


def test_a_change_after_the_first_event_is_a_second_version(handler):
    handle()
    handler.invoice["amount"]["value"] = "99.00"
    handle()
    assert count(InvoiceVersion) == 2


def test_a_paused_monitor_ignores_events(handler):
    with SessionLocal() as db:
        monitor._state(db, monitor.account_id()).state = "PAUSED"
        db.commit()
    handle()
    assert count(InvoiceVersion) == 0 and not handler.calls


def test_a_failing_read_does_not_raise_and_stores_nothing(monkeypatch, handler):
    async def broken(method, path, json=None, client=None):
        raise HTTPException(502, "PayPal error 500")

    monkeypatch.setattr(paypal, "paypal_request", broken)
    handle()
    assert count(InvoiceVersion) == 0


def test_polling_after_a_webhook_finds_nothing_new(handler):
    handle()
    handler.invoice["detail"]["metadata"]["create_time"] = "2026-10-02T00:00:00Z"  # as the list returns it, unchanged
    item = deepcopy(handler.invoice)
    item.pop("items")
    item["detail"]["metadata"].pop("last_update_time")

    async def listing(created_from, created_to):
        return [item], 1

    paypal_list = paypal.list_invoice_items
    paypal.list_invoice_items = listing
    try:
        async def run():
            with SessionLocal() as db:
                return await monitor.sync_once(db)
        result = asyncio.run(run())
    finally:
        paypal.list_invoice_items = paypal_list
    assert result["new"] == 0 and count(InvoiceVersion) == 1

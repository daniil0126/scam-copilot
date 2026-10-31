"""PayPal webhooks for the account's own invoices: a signal that an invoice changed, so it need not wait for the poll.

Only the issuer's app receives these (a recipient gets nothing), and the event is a hint, never a source of data:
- the signature is verified with PayPal (`verify-webhook-signature`); an event that does not verify is dropped;
- from the event only the invoice id is taken. The invoice is then read from PayPal and goes through the same
  pipeline as a polling pass (normalize, hash, new version, check). Events arrive in batches, out of order, and carry
  the invoice as it was at delivery time, not at the event time, so the body is not trusted for content;
- the same version arriving through several events (or through the poll) is stored once, by its content hash.
Polling stays on as the fallback for events that were never delivered. Off unless `PAYPAL_WEBHOOK_ID` is set.
"""
import asyncio
import logging
import os
import re
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from app import monitor, paypal
from app.db import SessionLocal

log = logging.getLogger("monitor")
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

INVOICE_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")  # it goes into a PayPal URL path, so nothing else is allowed through
MAX_BODY = 200_000
SIGNATURE_HEADERS = {
    "auth_algo": "paypal-auth-algo", "cert_url": "paypal-cert-url", "transmission_id": "paypal-transmission-id",
    "transmission_sig": "paypal-transmission-sig", "transmission_time": "paypal-transmission-time",
}
_tasks: set[asyncio.Task] = set()
_lock = asyncio.Lock()  # one webhook handled at a time; a batch of events for one invoice is then read in turn


async def verify_signature(headers, event: dict, webhook_id: str) -> bool:
    body = {"webhook_id": webhook_id, "webhook_event": event}
    for field, header in SIGNATURE_HEADERS.items():
        if not (value := headers.get(header)):
            return False
        body[field] = value
    try:
        res = await paypal.paypal_request("POST", "/v1/notifications/verify-webhook-signature", body)
    except HTTPException as e:
        log.warning("webhook signature could not be checked: %s", e.detail)
        return False
    return res.get("verification_status") == "SUCCESS"


def invoice_id_of(event: dict) -> str | None:
    """The invoice an invoicing event is about, or None for anything else or an id of an unexpected shape."""
    if not str(event.get("event_type", "")).startswith("INVOICING.INVOICE."):
        return None
    resource = event.get("resource")
    invoice = resource.get("invoice") if isinstance(resource, dict) else None
    invoice_id = invoice.get("id") if isinstance(invoice, dict) else None
    return invoice_id if isinstance(invoice_id, str) and INVOICE_ID.match(invoice_id) else None


async def handle(invoice_id: str, event_type: str) -> None:
    async with _lock:
        try:
            with SessionLocal() as db:
                account = monitor.account_id()
                if monitor._state(db, account).state == "PAUSED":
                    log.info("webhook %s for %s ignored: monitoring paused", event_type, invoice_id)
                    return
                detail = await paypal.paypal_request("GET", f"/v2/invoicing/invoices/{invoice_id}")
                new = await monitor.store_version(db, account, invoice_id, detail, None, frozenset(), datetime.now(timezone.utc))
                log.info("webhook %s for %s: %s", event_type, invoice_id, "new version" if new else "nothing new")
        except Exception as e:  # nothing to retry here: the next polling pass reads the invoice again
            log.warning("webhook for %s failed: %s", invoice_id, monitor._describe(e))


@router.post("/paypal")
async def receive(request: Request):
    webhook_id = os.getenv("PAYPAL_WEBHOOK_ID")
    if not webhook_id:
        raise HTTPException(503, "Webhooks are not enabled.")
    if int(request.headers.get("content-length") or 0) > MAX_BODY:
        raise HTTPException(413, "Event is too large.")
    try:
        event = await request.json()
    except ValueError:
        raise HTTPException(400, "The body is not JSON.")
    if not isinstance(event, dict):
        raise HTTPException(400, "The body is not an event.")
    if not await verify_signature(request.headers, event, webhook_id):
        raise HTTPException(401, "The signature did not verify.")

    invoice_id = invoice_id_of(event)
    if invoice_id is None:
        return {"accepted": False, "reason": "not an invoice event"}
    # Answer at once: PayPal retries an event that is not acknowledged quickly, and the reading can take seconds.
    task = asyncio.create_task(handle(invoice_id, event["event_type"]))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return {"accepted": True, "invoiceId": invoice_id}

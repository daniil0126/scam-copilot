"""Background monitoring: polls PayPal for the account's invoices, stores each new version once, and checks it.

PayPal's search has no "updated since" filter, only date ranges on creation, invoice, due and payment dates.
So every pass re-lists a recent window (`LOOKBACK`) and tells what changed by hash:
- a list item that hashes as last time is skipped without a detail request;
- otherwise the invoice is loaded in full, normalized and hashed, and a version not seen before is stored and checked.
A change that shows up only in the full invoice (such as items) and not in the list item is noticed when the list
item changes too; the list item does not carry items.
"""
import asyncio
import hashlib
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import paypal
from app.checks import run_check
from app.db import SessionLocal, get_db
from app.models import Check, InvoiceVersion, MonitoredInvoice, SyncState
from app.normalize import normalize_paypal
from app.paypal import to_invoice

log = logging.getLogger("monitor")
if not log.handlers:  # uvicorn leaves other loggers silent below WARNING; the monitor's own lines should show in the console
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("INFO:     monitor: %(message)s"))
    log.addHandler(_handler)
    log.setLevel(logging.INFO)
    log.propagate = False

INTERVAL = int(os.getenv("MONITOR_INTERVAL_SECONDS", "60"))
LOOKBACK = timedelta(days=30)  # invoices created in this period are re-read on every pass
OVERLAP = timedelta(minutes=10)  # extra margin before the checkpoint when catching up after a long stop

router = APIRouter(prefix="/monitoring", tags=["monitoring"])
_lock = asyncio.Lock()  # one pass at a time
_jobs: set[asyncio.Task] = set()


def account_id() -> str:
    """One account for now: the PayPal app whose credentials the backend holds. The column stays for several accounts."""
    return "acc_" + hashlib.sha256((paypal.PAYPAL_CLIENT_ID or "").encode()).hexdigest()[:8]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _naive(moment: datetime) -> datetime:
    return moment.astimezone(timezone.utc).replace(tzinfo=None)  # the database keeps naive UTC


def _aware(moment: datetime) -> datetime:
    return moment.replace(tzinfo=timezone.utc)


def _iso(moment: datetime | None) -> str | None:
    return _aware(moment).strftime("%Y-%m-%dT%H:%M:%SZ") if moment else None


def _describe(error: Exception) -> str:
    return str(getattr(error, "detail", None) or error) or type(error).__name__


def _state(db: Session, account: str) -> SyncState:
    state = db.get(SyncState, account)
    if state is None:
        state = SyncState(account_id=account, state="ACTIVE")
        db.add(state)
        db.commit()
    return state


async def _process(db: Session, account: str, item: dict, pending: frozenset[str], now: datetime) -> bool:
    """Handles one list item. True when it produced a version that was not stored before."""
    invoice_id = item["id"]
    list_hash = normalize_paypal(item).contentHash
    known = db.get(MonitoredInvoice, (account, invoice_id))
    if known and known.list_hash == list_hash:
        known.last_synced_at = _naive(now)
        db.commit()
        return False

    detail = await paypal.paypal_request("GET", f"/v2/invoicing/invoices/{invoice_id}")
    invoice = normalize_paypal(detail, account)
    if known and known.current_version_hash == invoice.contentHash:
        known.list_hash, known.last_synced_at = list_hash, _naive(now)
        db.commit()
        return False

    # Checked before the version is stored: if the check fails the version stays unseen and the next pass retries.
    await run_check(db, invoice_id, to_invoice(detail), pending)
    stored = db.scalar(select(InvoiceVersion.row_id).where(
        InvoiceVersion.account_id == account, InvoiceVersion.invoice_id == invoice_id,
        InvoiceVersion.content_hash == invoice.contentHash,
    ))
    if stored is None:
        db.add(InvoiceVersion(
            account_id=account, invoice_id=invoice_id, content_hash=invoice.contentHash,
            normalized=invoice.model_dump(mode="json"), raw=detail, seen_at=_naive(now),
        ))
    if known:
        known.current_version_hash, known.list_hash, known.last_synced_at = invoice.contentHash, list_hash, _naive(now)
    else:
        db.add(MonitoredInvoice(
            account_id=account, id=invoice_id, current_version_hash=invoice.contentHash, list_hash=list_hash,
            first_seen_at=_naive(now), last_synced_at=_naive(now),
        ))
    db.commit()
    return stored is None


async def sync_once(db: Session) -> dict:
    """One pass over the recent window. The checkpoint moves only when everything in the pass succeeded."""
    account = account_id()
    state = _state(db, account)
    if state.state == "PAUSED":
        return {"skipped": True, "new": 0, "failed": 0}

    started = _now()
    start = started - LOOKBACK
    if state.last_successful_sync_at:
        start = min(start, _aware(state.last_successful_sync_at) - OVERLAP)

    try:
        items, total = await paypal.list_invoice_items(created_from=start, created_to=started)
    except Exception as e:
        log.warning("listing failed: %s", _describe(e))
        db.rollback()
        state.state, state.last_error = "ERROR", f"PayPal listing failed: {_describe(e)}"
        db.commit()
        return {"skipped": False, "new": 0, "failed": 1}

    # Oldest first, and invoices of this pass not processed yet stay out of the history, as in the bulk check.
    items.sort(key=lambda i: ((i.get("detail") or {}).get("metadata", {}).get("create_time", ""), i["id"]))
    pending = {i["id"] for i in items}
    new, errors = 0, []
    for item in items:
        db.refresh(state)  # a pause pressed during the pass must stop it before the next invoice, not after the last
        if state.state == "PAUSED":
            log.info("pass stopped: monitoring paused")
            return {"skipped": True, "new": new, "failed": len(errors)}
        pending.discard(item["id"])
        try:
            new += await _process(db, account, item, frozenset(pending), started)
        except Exception as e:  # one broken invoice must not stop the rest
            db.rollback()
            log.warning("invoice %s failed: %s", item["id"], _describe(e))
            errors.append(f"{item['id']}: {_describe(e)}")

    db.refresh(state)
    if state.state != "PAUSED":  # paused during the pass: stays paused
        if errors:
            state.state, state.last_error = "ERROR", f"{len(errors)} invoice(s) failed, first: {errors[0]}"
        else:
            state.state, state.last_successful_sync_at = "ACTIVE", _naive(started)
            state.last_error = f"Window holds {total} invoices, only {len(items)} were read" if total > len(items) else None
        db.commit()
    log.info("pass done: window=%d invoices, new=%d, failed=%d", len(items), new, len(errors))
    return {"skipped": False, "new": new, "failed": len(errors)}


async def _loop() -> None:
    while True:
        try:
            async with _lock:
                with SessionLocal() as db:
                    await sync_once(db)
        except Exception:
            log.exception("monitor pass crashed")
        await asyncio.sleep(INTERVAL)


@asynccontextmanager
async def lifespan(app):
    """Starts polling when PayPal credentials are set and the interval is above zero."""
    task = None
    if INTERVAL > 0 and paypal.PAYPAL_CLIENT_ID and paypal.PAYPAL_CLIENT_SECRET:
        with SessionLocal() as db:
            log.info("started, every %ds, state %s", INTERVAL, _state(db, account_id()).state)
        task = asyncio.create_task(_loop())
    else:
        log.info("not started (no PayPal credentials or MONITOR_INTERVAL_SECONDS=0)")
    yield
    if task:
        task.cancel()


RECENT_EVENTS = 20


def _recent_events(db: Session, account: str) -> list[dict]:
    """Latest stored versions, newest first. The first version of an invoice is NEW_INVOICE, later ones INVOICE_UPDATED.

    Risk comes from the invoice's current entry in `checks`, which can be newer than the version the event is about.
    """
    versions = db.scalars(
        select(InvoiceVersion).where(InvoiceVersion.account_id == account)
        .order_by(InvoiceVersion.seen_at.desc(), InvoiceVersion.row_id.desc()).limit(RECENT_EVENTS)
    ).all()
    events = []
    for v in versions:
        first = db.scalar(select(func.min(InvoiceVersion.row_id)).where(
            InvoiceVersion.account_id == account, InvoiceVersion.invoice_id == v.invoice_id))
        check = db.scalars(select(Check).where(Check.paypal_invoice_id == v.invoice_id)).first()
        result = check.result if check else {}
        n = v.normalized
        events.append({
            "invoiceId": v.invoice_id,
            "eventType": "NEW_INVOICE" if v.row_id == first else "INVOICE_UPDATED",
            "detectedAt": _iso(v.seen_at),
            "invoiceNumber": n.get("invoiceNumber"),
            "senderName": n.get("senderName"),
            "amount": n.get("amount"),
            "currency": n.get("currency"),
            "status": n.get("status"),
            "riskLevel": result.get("level"),
            "signals": [f["label"] for f in result.get("findings", []) if f.get("severity") != "ok"],
        })
    return events


@router.get("")
def get_monitoring(db: Session = Depends(get_db)):
    account = account_id()
    state = _state(db, account)
    mine = select(MonitoredInvoice.id).where(MonitoredInvoice.account_id == account)
    total = db.scalar(select(func.count()).select_from(MonitoredInvoice).where(MonitoredInvoice.account_id == account))
    levels = [r["level"] for r in db.scalars(select(Check.result).where(Check.paypal_invoice_id.in_(mine)))]
    return {
        "state": state.state,
        "lastSuccessfulSyncAt": _iso(state.last_successful_sync_at),
        "totalInvoices": total,
        "highRisk": levels.count("high"),
        "criticalRisk": levels.count("critical"),
        "potentialDuplicates": 0,  # not computed yet (plan 06)
        "vendorAnomalies": 0,  # not computed yet (plan 06)
        "recentEvents": _recent_events(db, account),
        "errors": [state.last_error] if state.last_error else [],
    }


def _set_state(db: Session, value: str) -> dict:
    state = _state(db, account_id())
    state.state = value
    db.commit()
    return {"state": state.state}


@router.post("/pause")
def pause(db: Session = Depends(get_db)):
    return _set_state(db, "PAUSED")


@router.post("/resume")
def resume(db: Session = Depends(get_db)):
    return _set_state(db, "ACTIVE")


@router.post("/sync")
async def sync(db: Session = Depends(get_db)):
    """Starts a pass now and returns at once."""
    if _state(db, account_id()).state == "PAUSED":
        raise HTTPException(409, "Monitoring is paused")

    async def job():
        try:
            async with _lock:
                with SessionLocal() as own:
                    await sync_once(own)
        except Exception:
            log.exception("manual sync crashed")

    task = asyncio.create_task(job())
    _jobs.add(task)
    task.add_done_callback(_jobs.discard)
    return {"jobId": str(uuid.uuid4())}

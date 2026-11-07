"""Hand-off to PayPal's payment page for invoices with no warning signs (docs/plans/16-pay-safe-invoices.md).

Scam Copilot never moves money. PayPal's Invoicing API has no call that pays an invoice on the payer's behalf
(`record_payment_for_invoice` is the issuer's bookkeeping), so a payment is the payer opening the invoice's own PayPal page.
What this module decides is whether the app may *lead* the user there, and it decides on the server:

- `preview` answers from what the monitor has stored (no PayPal call), so a list can show Pay buttons cheaply;
- `intents` re-reads each invoice from PayPal, takes the content hash of what is there now, and only an invoice whose
  exact version was analysed as low risk gets a link. An invoice changed after its check is refused (`changed`);
- the link is the `recipient_view_url` PayPal itself returned, accepted only for PayPal's host, path and invoice id;
- the model behind the chat has no tool that reaches `intents`: it can only *propose* (agent.py), a person confirms.

Every state-changing call needs the `X-Requested-By` header, which makes a browser send a preflight first, so a web page
cannot trigger it against a locally running backend. The `pay_intents` table is defined here, on the shared `Base`.
"""
import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import JSON, DateTime, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app import audit_log, paypal
from app.db import Base, get_db
from app.models import InvoiceVersion, MonitoredInvoice
from app.normalize import normalize_paypal
from app.reports.models import Analysis
from app.security import current_account

router = APIRouter(prefix="/payments", tags=["payments"])

MAX_BASKET = 10  # invoices in one confirmation
MAX_PREVIEW = 50
INTENT_TTL = timedelta(minutes=10)
PAYABLE_STATUSES = {"SENT", "UNPAID", "PARTIALLY_PAID"}
PAID_STATUSES = {"PAID", "MARKED_AS_PAID"}
PAGE_HOSTS = {"sandbox": {"www.sandbox.paypal.com"}, "live": {"www.paypal.com"}}

REASON_TEXT = {
    "not_checked": "Not checked yet",
    "changed": "Changed since its check",
    "paid": "Already paid",
    "not_payable": "Not open for payment",
    "risk_high": "High risk",
    "risk_medium": "Medium risk",
    "duplicate": "Possible duplicate",
    "no_page": "No safe PayPal payment page",
    "unavailable": "Could not be read from PayPal",
    "over_limit": "Over the payment limit",
}


class PayIntent(Base):
    """A payment page the user was led to. `OPENED` means the link was opened, never that money moved: `PAID` is set only
    when PayPal itself reports the invoice paid."""

    __tablename__ = "pay_intents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String, index=True)
    account_id: Mapped[str] = mapped_column(String, index=True)
    invoice_id: Mapped[str] = mapped_column(String, index=True)
    content_hash: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, default="ui")  # ui / chat: where the person started it
    amount: Mapped[str] = mapped_column(String)
    currency: Mapped[str] = mapped_column(String)
    supplier: Mapped[str] = mapped_column(String, default="")
    number: Mapped[str] = mapped_column(String, default="")
    risk_level: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="ISSUED")  # ISSUED / OPENED / PAID / EXPIRED / CANCELLED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


def require_ui(x_requested_by: str | None = Header(default=None)) -> None:
    if x_requested_by != "scamcopilot-ui":
        raise HTTPException(403, "Missing X-Requested-By header")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(moment: datetime | None) -> str | None:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ") if moment else None


def _money(value) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


def totals_of(items: list[dict]) -> dict[str, str]:
    """Sums per currency; amounts in different currencies are never added together."""
    out: dict[str, Decimal] = {}
    for item in items:
        amount = _money(item.get("amount"))
        if amount is not None and item.get("currency"):
            out[item["currency"]] = out.get(item["currency"], Decimal(0)) + amount
    return {cur: f"{total:.2f}" for cur, total in sorted(out.items())}


def pay_url(raw: dict, invoice_id: str) -> str | None:
    """The invoice's payer page, only if it is PayPal's own page for exactly this invoice."""
    url = ((raw.get("detail") or {}).get("metadata") or {}).get("recipient_view_url")
    if not isinstance(url, str) or "\\" in url or any(c.isspace() for c in url):
        return None
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return None
    hosts = PAGE_HOSTS["live" if paypal.PAYPAL_MODE == "live" else "sandbox"]
    expected = invoice_id.removeprefix("INV2-").replace("-", "").upper()
    ok = (
        parts.scheme == "https" and parts.hostname in hosts and not parts.username and not parts.password
        and port in (None, 443) and parts.path.startswith("/invoice/p/") and not parts.query
        and parts.fragment.upper() == expected and bool(expected)
    )
    return url if ok else None


def _limit() -> Decimal | None:
    return _money(os.getenv("PAY_MAX_TOTAL")) if os.getenv("PAY_MAX_TOTAL") else None


def _analysis(db: Session, account: str, invoice_id: str, content_hash: str) -> Analysis | None:
    return db.scalars(select(Analysis).where(
        Analysis.account_id == account, Analysis.invoice_id == invoice_id, Analysis.content_hash == content_hash,
    ).order_by(Analysis.analyzed_at.desc()).limit(1)).first()


def judge(db: Session, account: str, invoice_id: str, normalized: dict, raw: dict, content_hash: str) -> dict:
    """The gate. `content_hash` is the version that is being judged: the stored one for a preview, the one PayPal returned a
    moment ago for an intent. Only an analysis of exactly that version counts."""
    reasons: list[str] = []
    level = None
    checked_at = None
    limited = False

    status = (normalized.get("status") or "").upper()
    due = _money((raw.get("due_amount") or {}).get("value"))
    if status in PAID_STATUSES or (due is not None and due <= 0 and status not in {"DRAFT", "CANCELLED"}):
        reasons.append("paid")
    elif status not in PAYABLE_STATUSES:
        reasons.append("not_payable")

    analysis = _analysis(db, account, invoice_id, content_hash)
    if analysis is None:
        earlier = db.scalar(select(Analysis.row_id).where(Analysis.account_id == account, Analysis.invoice_id == invoice_id).limit(1))
        reasons.append("changed" if earlier is not None else "not_checked")
    else:
        checked_at = analysis.analyzed_at
        stored = analysis.risk_level
        level = {"LOW": "low", "MEDIUM": "medium"}.get(stored, "high")
        if level == "high":
            reasons.append("risk_high")
        elif level == "medium":
            reasons.append("risk_medium")
        signals = (analysis.result or {}).get("signals") or []
        if any(s.get("status") == "DETECTED" and str(s.get("type", "")).startswith("DUPLICATE") for s in signals):
            reasons.append("duplicate")
        # A first invoice from a supplier has no history to compare with; that is shown, but it is not a warning sign.
        limited = any(s.get("status") == "INSUFFICIENT_DATA" for s in signals)

    if not reasons and pay_url(raw, invoice_id) is None:
        reasons.append("no_page")

    amount = _money(normalized.get("amount"))
    shown = due if due is not None and due > 0 else amount  # what is still owed, for a part-paid invoice
    return {
        "invoiceId": invoice_id,
        "eligible": not reasons,
        "reasons": [{"code": c, "text": REASON_TEXT[c]} for c in reasons],
        "supplier": normalized.get("senderName"),
        "number": normalized.get("invoiceNumber"),
        "amount": f"{shown:.2f}" if shown is not None else None,
        "currency": normalized.get("currency"),
        "dueDate": normalized.get("dueDate"),
        "status": normalized.get("status"),
        "level": level,
        "checkedAt": _iso(checked_at),
        "limited": limited,
        "contentHash": content_hash,
    }


def _public(view: dict) -> dict:
    return {k: v for k, v in view.items() if k != "contentHash"}


def stored_view(db: Session, account: str, invoice_id: str) -> dict:
    """The gate's answer from stored data only (no PayPal call): what the monitor last saw and analysed."""
    known = db.get(MonitoredInvoice, (account, invoice_id))
    version = known and db.scalars(select(InvoiceVersion).where(
        InvoiceVersion.account_id == account, InvoiceVersion.invoice_id == invoice_id,
        InvoiceVersion.content_hash == known.current_version_hash)).first()
    if not version:
        return {"invoiceId": invoice_id, "eligible": False, "reasons": [{"code": "not_checked", "text": REASON_TEXT["not_checked"]}],
                "supplier": None, "number": None, "amount": None, "currency": None, "dueDate": None, "status": None,
                "level": None, "checkedAt": None, "limited": False, "contentHash": ""}
    return judge(db, account, invoice_id, version.normalized, version.raw, version.content_hash)


async def read_invoice(invoice_id: str) -> dict | None:
    """The invoice as PayPal returns it now, or None when PayPal refused or could not be reached."""
    try:
        return await paypal.paypal_request("GET", f"/v2/invoicing/invoices/{paypal.valid_invoice_id(invoice_id)}")
    except Exception:  # an HTTPException from paypal_request included
        return None


def judge_fresh(db: Session, account: str, invoice_id: str, raw: dict | None) -> dict:
    """The gate's answer for an invoice as PayPal returned it (None: could not be read)."""
    try:
        normalized = normalize_paypal(raw or {}, account) if raw is not None else None
    except Exception:
        normalized = None
    if raw is None or normalized is None:
        return {"invoiceId": invoice_id, "eligible": False, "reasons": [{"code": "unavailable", "text": REASON_TEXT["unavailable"]}],
                "supplier": None, "number": None, "amount": None, "currency": None, "dueDate": None, "status": None,
                "level": None, "checkedAt": None, "limited": False, "contentHash": ""}
    return judge(db, account, invoice_id, normalized.model_dump(mode="json"), raw, normalized.contentHash)


async def fresh_view(db: Session, account: str, invoice_id: str) -> tuple[dict, dict | None]:
    raw = await read_invoice(invoice_id)
    return judge_fresh(db, account, invoice_id, raw), raw


# --- routes ----------------------------------------------------------------------------------------------------------

class PreviewBody(BaseModel):
    invoiceIds: list[str] = Field(min_length=1, max_length=MAX_PREVIEW)


def _ids(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        value = paypal.valid_invoice_id(value)
        if value not in seen:
            seen.append(value)
    return seen


@router.post("/preview")
def preview(body: PreviewBody, account: str = Depends(current_account), db: Session = Depends(get_db)):
    """Who may be paid, from stored data. No side effects, no links."""
    items = [_public(stored_view(db, account, i)) for i in _ids(body.invoiceIds)]
    return {"items": items, "totals": totals_of([i for i in items if i["eligible"]])}


class IntentsBody(BaseModel):
    invoiceIds: list[str] = Field(min_length=1, max_length=MAX_BASKET)
    source: str = Field(default="ui", pattern="^(ui|chat)$")
    expectedIds: list[str] | None = None  # what the person saw in the confirmation; any difference means "ask again"
    expectedTotals: dict[str, str] | None = None


def _refuse(db: Session, account: str, views: list[dict], code: str, body: IntentsBody, message: str) -> JSONResponse:
    eligible = [v for v in views if v["eligible"]]
    audit_log.record(db, account, "pay.blocked", {
        "code": code, "source": body.source, "requested": len(views),
        "reasons": {v["invoiceId"]: [r["code"] for r in v["reasons"]] for v in views if not v["eligible"]},
    })
    db.commit()
    return JSONResponse(status_code=409, content={"error": {"code": code, "message": message},
                                                  "items": [_public(v) for v in views], "totals": totals_of(eligible)})


@router.post("/intents", dependencies=[Depends(require_ui)])
async def create_intents(body: IntentsBody, account: str = Depends(current_account), db: Session = Depends(get_db)):
    """Re-checks every invoice against PayPal now and, only if all of them pass, returns their payment pages."""
    ids = _ids(body.invoiceIds)
    # PayPal is asked about all of them at once: a basket of ten would otherwise wait for ten calls in a row.
    reads = await asyncio.gather(*(read_invoice(i) for i in ids))
    raws = dict(zip(ids, reads))
    views = [judge_fresh(db, account, i, raws[i]) for i in ids]

    if any(not v["eligible"] for v in views):
        return _refuse(db, account, views, "changed", body, "Some invoices can no longer be paid from here. Review the list again.")
    totals = totals_of(views)
    if body.expectedIds is not None and (set(_ids(body.expectedIds)) != set(ids) or (body.expectedTotals or {}) != totals):
        return _refuse(db, account, views, "changed", body, "The invoices changed since you reviewed them. Review the list again.")
    limit = _limit()
    if limit is not None and any(Decimal(t) > limit for t in totals.values()):
        for v in views:
            v["eligible"], v["reasons"] = False, [{"code": "over_limit", "text": REASON_TEXT["over_limit"]}]
        return _refuse(db, account, views, "over_limit", body, f"One payment may not exceed {limit} per currency.")

    now = _now()
    batch = str(uuid.uuid4())
    out = []
    for view in views:
        invoice_id = view["invoiceId"]
        active = db.scalars(select(PayIntent).where(
            PayIntent.account_id == account, PayIntent.invoice_id == invoice_id, PayIntent.content_hash == view["contentHash"],
            PayIntent.status.in_(("ISSUED", "OPENED")), PayIntent.expires_at > now)).first()
        if active is None:
            active = PayIntent(
                id=str(uuid.uuid4()), batch_id=batch, account_id=account, invoice_id=invoice_id, content_hash=view["contentHash"],
                source=body.source, amount=view["amount"] or "", currency=view["currency"] or "", supplier=view["supplier"] or "",
                number=view["number"] or "", risk_level=view["level"] or "", status="ISSUED", created_at=now, expires_at=now + INTENT_TTL)
            db.add(active)
        out.append({"intentId": active.id, "invoiceId": invoice_id, "url": pay_url(raws[invoice_id], invoice_id),
                    "expiresAt": _iso(active.expires_at), "supplier": view["supplier"], "number": view["number"],
                    "amount": view["amount"], "currency": view["currency"], "status": active.status})
    audit_log.record(db, account, "pay.intent_created", {"batch": batch, "source": body.source, "count": len(out),
                                                         "invoices": ids, "totals": totals})
    db.commit()
    return {"batchId": batch, "intents": out, "totals": totals}


def _own(db: Session, account: str, intent_id: str) -> PayIntent:
    intent = db.get(PayIntent, intent_id)
    if intent is None or intent.account_id != account:
        raise HTTPException(404, "Unknown payment")
    return intent


@router.post("/intents/{intent_id}/opened", dependencies=[Depends(require_ui)])
def mark_opened(intent_id: str, account: str = Depends(current_account), db: Session = Depends(get_db)):
    intent = _own(db, account, intent_id)
    if intent.status == "ISSUED" and intent.expires_at <= _now():
        intent.status = "EXPIRED"
    if intent.status not in ("ISSUED", "OPENED"):
        db.commit()
        raise HTTPException(409, f"This payment is {intent.status.lower()}")
    if intent.status == "ISSUED":
        intent.status, intent.opened_at = "OPENED", _now()
        audit_log.record(db, account, "pay.link_opened", {"intent": intent.id, "invoice": intent.invoice_id, "source": intent.source})
    db.commit()
    return {"intentId": intent.id, "status": intent.status}


@router.post("/intents/{intent_id}/cancel", dependencies=[Depends(require_ui)])
def cancel(intent_id: str, account: str = Depends(current_account), db: Session = Depends(get_db)):
    intent = _own(db, account, intent_id)
    if intent.status in ("ISSUED", "OPENED"):
        intent.status = "CANCELLED"
        audit_log.record(db, account, "pay.cancelled", {"intent": intent.id, "invoice": intent.invoice_id})
    db.commit()
    return {"intentId": intent.id, "status": intent.status}


@router.get("/intents")
async def intent_status(ids: str = Query(..., max_length=2000), account: str = Depends(current_account), db: Session = Depends(get_db)):
    """The state of payments the user was led to. An opened one is re-read from PayPal: `PAID` comes from PayPal only."""
    wanted = [i for i in ids.split(",") if i][:MAX_BASKET * 3]
    rows = [r for r in (db.get(PayIntent, i) for i in wanted) if r is not None and r.account_id == account]
    now = _now()
    paid_now: list[tuple[str, dict]] = []
    for row in rows:
        if row.status == "ISSUED" and row.expires_at <= now:
            row.status = "EXPIRED"
        if row.status == "OPENED":
            try:
                raw = await paypal.paypal_request("GET", f"/v2/invoicing/invoices/{paypal.valid_invoice_id(row.invoice_id)}")
            except Exception:
                continue  # the state stays OPENED: not confirmed
            if str(raw.get("status", "")).upper() in PAID_STATUSES:
                row.status = "PAID"
                paid_now.append((row.invoice_id, raw))
    db.commit()
    if paid_now:
        # History and the gate read stored versions: store what PayPal just said, so a paid invoice shows as paid at once
        # instead of after the monitor's next pass.
        from app import monitor

        for invoice_id, raw in paid_now:
            try:
                await monitor.store_version(db, account, invoice_id, raw, None, frozenset(), monitor._now())
            except Exception:
                db.rollback()  # the monitor will store it on its next pass
    return {"items": [{"intentId": r.id, "invoiceId": r.invoice_id, "status": r.status} for r in rows]}


class CheckBody(BaseModel):
    invoiceId: str


@router.post("/check", dependencies=[Depends(require_ui)])
async def check_now(body: CheckBody, account: str = Depends(current_account), db: Session = Depends(get_db)):
    """Runs the monitor's own pipeline (check, alert, analysis, stored version) on the invoice as PayPal has it now."""
    from app import monitor

    invoice_id = paypal.valid_invoice_id(body.invoiceId)
    raw = await paypal.paypal_request("GET", f"/v2/invoicing/invoices/{invoice_id}")
    await monitor.store_version(db, account, invoice_id, raw, None, frozenset(), monitor._now())
    view, _ = await fresh_view(db, account, invoice_id)
    return _public(view)

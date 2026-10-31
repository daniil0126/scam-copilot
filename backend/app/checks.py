import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app import llm
from app.db import get_db
from app.email_rules import page_findings
from app.models import Check, InvoiceEmail
from app.normalize import normalize_payer_page
from app.payer_page import MAX_TEXT, is_payer_page
from app.paypal import fetch_invoices, get_invoice
from app.normalize import Invoice
from app.scoring import apply_extra, score_invoice

router = APIRouter(prefix="/checks", tags=["checks"])


class CheckRequest(BaseModel):
    invoice_id: str


def legacy_invoice(inv: Invoice) -> dict:
    """The invoice in the flat shape `score_invoice` and the History table expect."""
    return {
        "number": inv.invoiceNumber or "",
        "supplier": {"name": inv.senderName or "", "email": inv.senderEmail or "", "phone": inv.senderPhone or ""},
        "note": inv.note or "",
        "amount": float(inv.amount) if inv.amount is not None else 0.0,
        "currency": inv.currency or "",
        "dueDate": inv.dueDate.isoformat() if inv.dueDate else "",
        "status": "",
    }


async def run_check(
    db: Session, invoice_id: str, invoice: dict, ignore: frozenset[str] = frozenset(), use_ai: bool = False,
    extra: dict | None = None,
) -> dict:
    """Scores an already loaded invoice against the history and stores the result.

    `ignore` lists PayPal invoice ids that must not serve as history (used by the bulk run).
    `use_ai` adds the LLM review (a no-op when no provider is configured).
    `extra` carries findings from another source (see `scoring.apply_extra`), added before the AI review and the save.
    """
    supplier = invoice["supplier"]

    # Re-checking the same PayPal invoice updates its entry instead of adding a duplicate.
    existing = db.scalars(select(Check).where(Check.paypal_invoice_id == invoice_id)).first()

    # History to compare with: other invoices only, never the invoice being checked.
    latest = (
        select(Check).where(Check.paypal_invoice_id.not_in(ignore | {invoice_id}))
        .order_by(desc(Check.checked_at)).limit(1)
    )
    previous = db.scalars(latest.where(Check.supplier_name == supplier["name"])).first()
    known_by_email = (
        db.scalars(latest.where(Check.supplier_email == supplier["email"])).first() if supplier["email"] else None
    )

    now = datetime.utcnow()
    result = {
        "id": existing.id if existing else str(uuid.uuid4()),
        "invoice": invoice,
        "checkedAt": now.isoformat(timespec="seconds") + "Z",  # stored as naive UTC
        **score_invoice(invoice, previous, known_by_email),
    }
    if extra:
        apply_extra(result, extra)
    if use_ai and (analysis := await llm.analyse_invoice(invoice, result)):
        llm.apply_analysis(result, analysis)
    fields = dict(
        paypal_invoice_id=invoice_id, supplier_name=supplier["name"], supplier_email=supplier["email"],
        number=invoice["number"], amount=invoice["amount"], currency=invoice["currency"], checked_at=now, result=result,
    )
    if existing:
        for key, value in fields.items():
            setattr(existing, key, value)
    else:
        db.add(Check(id=result["id"], **fields))
    db.commit()
    return result


@router.post("")
async def create_check(body: CheckRequest, db: Session = Depends(get_db)):
    return await run_check(db, body.invoice_id, await get_invoice(body.invoice_id), use_ai=True)


class PageCheckRequest(BaseModel):
    url: str = Field(max_length=2048)
    text: str = Field(max_length=MAX_TEXT)


@router.post("/page")
async def create_page_check(body: PageCheckRequest, db: Session = Depends(get_db)):
    """Checks an invoice from the text of a PayPal payer page, for invoices PayPal's API will not give us (not ours).

    The same invoice checked through the API and through its page updates one entry: the id is the same.
    """
    if not is_payer_page(body.url, body.text):
        raise HTTPException(422, "This is not a PayPal invoice page for the payer.")
    inv = normalize_payer_page(body.url, body.text)
    emails = db.scalars(select(InvoiceEmail).where(InvoiceEmail.invoice_id == inv.id).order_by(InvoiceEmail.row_id)).all()
    extra = (
        page_findings(inv.model_dump(mode="json"), [{**e.normalized, "kind": e.kind} for e in emails]) if emails else None
    )
    return await run_check(db, inv.id, legacy_invoice(inv), use_ai=True, extra=extra)


@router.post("/bulk")
async def create_bulk_check(ai: bool = False, db: Session = Depends(get_db)):
    """Checks every invoice of the PayPal account, oldest first, one at a time.

    Scoring compares an invoice with the supplier's history, so the order matters. Invoices of this batch
    that are not processed yet are kept out of the history, which makes a re-run give the same levels.
    Rules only by default: `?ai=true` also runs the LLM per invoice, which costs one model call each.
    Invoices are always re-scored (no PayPal call needed): the history may have changed since the last run.
    """
    listing = await fetch_invoices()
    entries = sorted(listing["invoices"], key=lambda e: (e["createdAt"], e["id"]))
    pending = {e["id"] for e in entries}
    results, errors = [], []
    for entry in entries:
        pending.discard(entry["id"])
        try:
            results.append(await run_check(db, entry["id"], entry["invoice"], frozenset(pending), use_ai=ai))
        except Exception as e:  # one broken invoice must not stop the rest
            db.rollback()
            errors.append({"invoiceId": entry["id"], "error": str(e) or type(e).__name__})
    summary = {level: sum(r["level"] == level for r in results) for level in ("low", "medium", "high")}
    return {
        "results": results,
        "errors": errors,
        "summary": {**summary, "total": len(results), "failed": len(errors)},
        "truncated": listing["truncated"],
    }


@router.get("")
def history(db: Session = Depends(get_db)):
    return [c.result for c in db.scalars(select(Check).order_by(desc(Check.checked_at)))]

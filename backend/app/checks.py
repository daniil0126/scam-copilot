import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app import llm
from app.db import get_db
from app.models import Check
from app.paypal import fetch_invoices, get_invoice
from app.scoring import score_invoice

router = APIRouter(prefix="/checks", tags=["checks"])


class CheckRequest(BaseModel):
    invoice_id: str


async def run_check(
    db: Session, invoice_id: str, invoice: dict, ignore: frozenset[str] = frozenset(), use_ai: bool = False
) -> dict:
    """Scores an already loaded invoice against the history and stores the result.

    `ignore` lists PayPal invoice ids that must not serve as history (used by the bulk run).
    `use_ai` adds the LLM review (a no-op when no provider is configured).
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

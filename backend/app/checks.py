import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Check
from app.paypal import get_invoice
from app.scoring import score_invoice

router = APIRouter(prefix="/checks", tags=["checks"])


class CheckRequest(BaseModel):
    invoice_id: str


@router.post("")
async def create_check(body: CheckRequest, db: Session = Depends(get_db)):
    invoice = await get_invoice(body.invoice_id)
    supplier = invoice["supplier"]

    # Re-checking the same PayPal invoice updates its entry instead of adding a duplicate.
    existing = db.scalars(select(Check).where(Check.paypal_invoice_id == body.invoice_id)).first()

    # History to compare with: other invoices only, never the invoice being checked.
    latest = select(Check).where(Check.paypal_invoice_id != body.invoice_id).order_by(desc(Check.checked_at)).limit(1)
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
    fields = dict(
        paypal_invoice_id=body.invoice_id, supplier_name=supplier["name"], supplier_email=supplier["email"],
        number=invoice["number"], amount=invoice["amount"], currency=invoice["currency"], checked_at=now, result=result,
    )
    if existing:
        for key, value in fields.items():
            setattr(existing, key, value)
    else:
        db.add(Check(id=result["id"], **fields))
    db.commit()
    return result


@router.get("")
def history(db: Session = Depends(get_db)):
    return [c.result for c in db.scalars(select(Check).order_by(desc(Check.checked_at)))]

"""What the rule engine knows about a sender, built from what this backend has stored (docs/plans/contracts.md, section 2).

`build_vendor_history` returns a plain dict with the fields of `VendorHistory`; the engine's own type is validated by
the caller (`VendorHistory.model_validate(...)`), so this module does not depend on the `rules` package.

Rules of the contract:
- only invoices created before the evaluated one, so that a repeated run gives the same result;
- the evaluated invoice itself is never in the history, but its earlier versions feed `knownContacts`: a payment email
  that changed between two versions is exactly what the engine looks for;
- `complete` is False when a limit cut the history, and the engine then lowers its confidence.
"""
import hashlib
import json
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Check, InvoiceVersion
from app.normalize import Invoice

SCAN_LIMIT = 2000  # newest stored versions read for one evaluation
MAX_PRIOR = 50
MAX_OTHER = 100


def sender_key(email: str | None, name: str | None) -> str:
    """The normalized sender email, otherwise the normalized name; empty when both are missing."""
    for value in (email, name):
        key = re.sub(r"\s+", " ", (value or "").strip().lower())
        if key:
            return key
    return ""


def _utc(moment: datetime | None) -> datetime | None:
    if moment is None:
        return None
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment.astimezone(timezone.utc)


def _parse(value) -> datetime | None:
    try:
        return _utc(datetime.fromisoformat(value.replace("Z", "+00:00"))) if isinstance(value, str) else None
    except ValueError:
        return None


def items_signature(items: list | None) -> str | None:
    """A hash of the normalized line items; None when the invoice has none."""
    rows = [
        [re.sub(r"\s+", " ", str(i.get(k) or "").strip().lower()) for k in ("name", "description", "quantity", "unitAmount")]
        for i in items or [] if isinstance(i, dict)
    ]
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest() if rows else None


def _historical(invoice_id: str, normalized: dict, created: datetime | None) -> dict:
    amount = normalized.get("amount")
    return {
        "id": invoice_id, "invoiceNumber": normalized.get("invoiceNumber"),
        "amount": None if amount is None else str(amount), "currency": normalized.get("currency"),
        "createdAt": created, "itemsSignature": items_signature(normalized.get("items")),
        "senderEmail": normalized.get("senderEmail"), "senderName": normalized.get("senderName"),
        "paymentLinks": normalized.get("paymentLinks"),
    }


def _contacts(snapshots: list[tuple[dict, datetime | None]]) -> list[dict]:
    """One entry per distinct (email, name, phone), with the first and last time it was seen."""
    found: dict[tuple, dict] = {}
    for normalized, seen in snapshots:
        key = tuple((normalized.get(k) or "").strip().lower() for k in ("senderEmail", "senderName", "senderPhone"))
        if not any(key):
            continue
        entry = found.setdefault(key, {
            "email": normalized.get("senderEmail"), "name": normalized.get("senderName"),
            "phone": normalized.get("senderPhone"), "firstSeen": seen, "lastSeen": seen,
        })
        if seen and (entry["firstSeen"] is None or seen < entry["firstSeen"]):
            entry["firstSeen"] = seen
        if seen and (entry["lastSeen"] is None or seen > entry["lastSeen"]):
            entry["lastSeen"] = seen
    return sorted(found.values(), key=lambda c: (c["firstSeen"] is None, c["firstSeen"] or datetime.min.replace(tzinfo=timezone.utc)))


def build_vendor_history(db: Session, account: str | None, invoice: Invoice) -> dict:
    key = sender_key(invoice.senderEmail, invoice.senderName)
    current_created = _utc(invoice.createdAt)

    versions = db.scalars(
        select(InvoiceVersion).where(InvoiceVersion.account_id == account)
        .order_by(InvoiceVersion.seen_at.desc(), InvoiceVersion.row_id.desc()).limit(SCAN_LIMIT)
    ).all() if account else []
    truncated = len(versions) >= SCAN_LIMIT

    latest: dict[str, tuple[dict, datetime | None]] = {}  # newest stored version of every invoice, by invoice id
    earlier_self: list[tuple[dict, datetime | None]] = []  # earlier versions of the evaluated invoice itself
    for v in versions:  # newest first
        seen = _utc(v.seen_at)
        if v.invoice_id == invoice.id:
            if v.content_hash != invoice.contentHash:
                earlier_self.append((v.normalized, seen))
            continue
        latest.setdefault(v.invoice_id, (v.normalized, seen))

    candidates: dict[str, tuple[dict, datetime | None, datetime | None]] = {  # id -> (normalized, created, seen)
        invoice_id: (normalized, _parse(normalized.get("createdAt")) or seen, seen)
        for invoice_id, (normalized, seen) in latest.items()
    }
    # Invoices checked from the payer side were never stored as versions; the check row is all that is known of them.
    for check in db.scalars(select(Check).order_by(Check.checked_at.desc()).limit(SCAN_LIMIT)):
        if check.paypal_invoice_id == invoice.id or check.paypal_invoice_id in candidates:
            continue
        seen = _utc(check.checked_at)
        candidates[check.paypal_invoice_id] = ({
            "invoiceNumber": check.number, "amount": check.amount, "currency": check.currency,
            "senderEmail": check.supplier_email or None, "senderName": check.supplier_name or None,
        }, seen, seen)

    prior: list[dict] = []
    other: list[dict] = []
    contacts: list[tuple[dict, datetime | None]] = list(earlier_self)
    for invoice_id, (normalized, created, seen) in candidates.items():
        if current_created and created and created >= current_created:
            continue  # created after the evaluated invoice: not history
        row = _historical(invoice_id, normalized, created)
        if sender_key(normalized.get("senderEmail"), normalized.get("senderName")) == key and key:
            prior.append(row)
            contacts.append((normalized, seen))
        else:
            other.append(row)

    def newest_first(rows: list[dict]) -> list[dict]:
        floor = datetime.min.replace(tzinfo=timezone.utc)
        return sorted(rows, key=lambda r: (r["createdAt"] or floor, r["id"]), reverse=True)

    prior, other = newest_first(prior), newest_first(other)
    total = len(prior)
    return {
        "senderKey": key,
        "priorInvoices": list(reversed(prior[:MAX_PRIOR])),  # oldest first, like /checks/bulk
        "knownContacts": _contacts(contacts),
        "otherSenderInvoices": other[:MAX_OTHER],
        "totalCount": total,
        "complete": not truncated and total <= MAX_PRIOR and len(other) <= MAX_OTHER,
    }

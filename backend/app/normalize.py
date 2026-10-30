"""Maps PayPal Invoicing API v2 responses to the normalized `Invoice` of docs/plans/contracts.md (section 1).

Nothing is guessed: a field that PayPal did not send stays None. `to_invoice` in paypal.py is kept for the old endpoints.
"""
import hashlib
import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel


class InvoiceItem(BaseModel):
    name: str | None = None
    description: str | None = None
    quantity: str | None = None
    unitAmount: str | None = None


class Invoice(BaseModel):
    id: str
    accountId: str | None = None
    source: Literal["paypal_api", "payer_page", "pdf"]
    invoiceNumber: str | None = None
    status: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    invoiceDate: date | None = None
    dueDate: date | None = None
    senderName: str | None = None
    senderLegalName: str | None = None  # payer page: the business behind a "doing business as" name
    senderEmail: str | None = None
    senderPhone: str | None = None
    recipientName: str | None = None
    recipientEmail: str | None = None
    paymentTerms: str | None = None
    items: list[InvoiceItem] | None = None
    paymentLinks: list[str] | None = None
    note: str | None = None
    createdAt: datetime | None = None
    updatedAt: datetime | None = None
    contentHash: str


# Fields that identify a version. Timestamps are left out: a change of `updatedAt` alone is not new content.
_HASH_EXCLUDED = {"contentHash", "createdAt", "updatedAt", "accountId"}


def content_hash(fields: dict) -> str:
    body = {k: v for k, v in fields.items() if k not in _HASH_EXCLUDED}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


_LINK = re.compile(r"(?:https?://|www\.)[^\s<>\"']+", re.IGNORECASE)


def extract_links(*texts: str | None) -> list[str]:
    """URLs written in the given texts, in order of appearance, without duplicates.

    Returned exactly as written (no lower-casing, no decoding, no network): judging a link, such as a lookalike
    domain, an IP address or punycode, is the rule engine's job and needs the original characters.
    """
    found: list[str] = []
    for text in texts:
        for match in _LINK.findall(text or ""):
            link = match.rstrip(".,;:!?)]}")
            if link and link not in found:
                found.append(link)
    return found


def _text(value) -> str | None:
    return value.strip() or None if isinstance(value, str) else None


def _decimal(value) -> Decimal | None:
    try:
        return Decimal(str(value)) if value is not None else None
    except InvalidOperation:
        return None


def _date(value) -> date | None:
    try:
        return date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def _datetime(value) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else None
    except ValueError:
        return None


def _name(person: dict) -> str | None:
    n = person.get("name") or {}
    return _text(person.get("business_name")) or _text(n.get("full_name")) or _text(
        " ".join(filter(None, [n.get("given_name"), n.get("surname")]))
    )


def _phone(person: dict) -> str | None:
    phones = person.get("phones") or []
    if not phones:
        return None
    return _text(" ".join(filter(None, [phones[0].get("country_code"), phones[0].get("national_number")])))


def normalize_paypal(raw: dict, account_id: str | None = None) -> Invoice:
    """`raw` is one invoice as returned by `GET /v2/invoicing/invoices/{id}` (or a list item, with fewer fields)."""
    detail = raw.get("detail") or {}
    meta = detail.get("metadata") or {}
    invoicer = raw.get("invoicer") or {}
    amount = raw.get("amount") or {}
    billing = ((raw.get("primary_recipients") or [{}])[0].get("billing_info")) or {}

    items = [
        InvoiceItem(
            name=_text(i.get("name")), description=_text(i.get("description")), quantity=_text(i.get("quantity")),
            unitAmount=_text((i.get("unit_amount") or {}).get("value")),
        )
        for i in raw.get("items") or []
    ] or None
    # Only the page links PayPal itself provides. `links[]` are API operations, not for the payer.
    note = "\n".join(filter(None, [detail.get("note"), detail.get("memo"), detail.get("terms_and_conditions")])) or None
    item_texts = [t for i in raw.get("items") or [] for t in (i.get("name"), i.get("description"))]
    own = _text(meta.get("recipient_view_url"))
    links = [*([own] if own else []), *extract_links(note, *item_texts)] or None
    email = _text(invoicer.get("email_address"))
    recipient_email = _text(billing.get("email_address"))
    term = detail.get("payment_term") or {}

    fields = dict(
        id=raw.get("id") or "",
        source="paypal_api",
        invoiceNumber=_text(detail.get("invoice_number")),
        status=_text(raw.get("status")),
        amount=_decimal(amount.get("value")),
        currency=_text(amount.get("currency_code") or detail.get("currency_code")),
        invoiceDate=_date(detail.get("invoice_date")),
        dueDate=_date(term.get("due_date")),
        senderName=_name(invoicer),
        senderEmail=email.lower() if email else None,
        senderPhone=_phone(invoicer),
        recipientName=_name(billing),
        recipientEmail=recipient_email.lower() if recipient_email else None,
        paymentTerms=_text(term.get("term_type")),
        items=[i.model_dump() for i in items] if items else None,
        paymentLinks=links,
        note=note,
    )
    currency = fields["currency"]
    fields["currency"] = currency.upper() if currency else None
    return Invoice(
        **{**fields, "items": items},
        accountId=account_id,
        createdAt=_datetime(meta.get("create_time")),
        updatedAt=_datetime(meta.get("last_update_time")),
        contentHash=content_hash(fields),
    )


def normalize_payer_page(url: str, text: str) -> Invoice:
    """Maps the text of a payer page to the normalized `Invoice` (source `payer_page`, no account)."""
    from app.payer_page import invoice_id_from_url, parse_payer_page

    page = parse_payer_page(text)
    items = [InvoiceItem(name=i["name"], description=i["description"], quantity=i["quantity"], unitAmount=i["unitAmount"])
             for i in page["items"] or []] or None
    fields = dict(
        id=invoice_id_from_url(url) or "page-" + hashlib.sha256(url.encode()).hexdigest()[:12],
        source="payer_page",
        invoiceNumber=page["number"],
        amount=page["amount"],
        currency=page["currency"],
        invoiceDate=page["issued"],
        dueDate=page["dueDate"],
        senderName=page["displayName"],
        senderLegalName=page["legalName"],
        senderEmail=page["senderEmail"],
        recipientName=page["recipientName"],
        recipientEmail=page["recipientEmail"],
        paymentTerms=page["dueText"],
        paymentLinks=extract_links(page["note"], *[t for i in page["items"] or [] for t in (i["name"], i["description"])]) or None,
        note=page["note"],
    )
    return Invoice(**fields, items=items, contentHash=content_hash({**fields, "items": [i.model_dump() for i in items] if items else None}))

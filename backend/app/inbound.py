"""Receives PayPal invoice notification emails (forwarded by the payer's mail filter, or posted by hand) and stores them.

Who may post: the extension itself (the browser puts its own `Origin: chrome-extension://<PROJECT_ID>` on the call and a
web page cannot claim that origin), or anyone who sends INBOUND_EMAIL_SECRET in `X-Inbound-Secret` (a mail filter that
forwards emails). Without one of the two nothing is read: anyone could post made-up emails and poison the history. The body is the HTML of the email (`Content-Type: text/html`), parsed and
never rendered. Each email is also checked (rules on its links and on what changed since the earlier email of the same
invoice) and the result goes to History like any other check. Only extracted fields are stored, and links lose their query strings (tracking and customer ids).
"""
import hashlib
import hmac
import os
from datetime import datetime
from urllib.parse import parse_qs, urlparse, urlunparse

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.checks import legacy_invoice, run_check
from app.db import get_db
from app.email_invoice import MAX_HTML, parse_invoice_email
from app.email_rules import assess_email
from app.models import Check, InvoiceEmail
from app.normalize import normalize_email

router = APIRouter(prefix="/inbound", tags=["inbound"])


def _bare(url: str) -> str:
    """The link without query and fragment: the part that tells where it goes, none of the ids that tell who clicked."""
    try:
        p = urlparse(url)
    except ValueError:
        return ""
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))


def _links(mail: dict) -> list[dict]:
    return [{"url": _bare(l["url"]), "text": l["text"][:200], "host": l["host"], "isPaypal": l["isPaypal"],
             "textMismatch": l["textMismatch"]} for l in mail["links"]]


def _authorize(request: Request) -> None:
    """The extension needs no secret (so "Check this email" works out of the box); every other caller needs INBOUND_EMAIL_SECRET."""
    project_id = os.getenv("PROJECT_ID")
    if project_id and request.headers.get("origin") == f"chrome-extension://{project_id}":
        return
    secret = os.getenv("INBOUND_EMAIL_SECRET")
    if not secret:
        raise HTTPException(503, "Inbound email is not enabled.")
    if not hmac.compare_digest((request.headers.get("x-inbound-secret") or "").encode(), secret.encode()):
        raise HTTPException(401, "Wrong or missing secret.")


@router.post("/email")
async def receive_email(request: Request, ai: bool = False, db: Session = Depends(get_db)):
    _authorize(request)
    if int(request.headers.get("content-length") or 0) > MAX_HTML * 4:  # bytes, UTF-8: a generous margin over characters
        raise HTTPException(413, "Email is too large.")
    html = (await request.body()).decode("utf-8", errors="replace")
    try:
        mail = parse_invoice_email(html)
    except ValueError:
        raise HTTPException(413, "Email is too large.")
    if mail["kind"] == "issuer_copy":
        raise HTTPException(422, "This is the confirmation PayPal sends to the issuer, not a notice for the payer.")
    if mail["kind"] == "unknown" and not mail["links"]:
        raise HTTPException(422, "This does not look like a PayPal invoice email.")

    invoice = normalize_email(html, mail)
    primary = mail["primaryLink"]
    delivery = (parse_qs(urlparse(primary["url"]).query).get("unptid") or [""])[0] if primary else ""  # PayPal's id of this send
    key = hashlib.sha256("|".join([
        mail["kind"], invoice.id, invoice.contentHash, (primary["host"] or "") if primary else "", delivery,
    ]).encode()).hexdigest()  # content and link host are in it, so a copy of a real delivery id cannot hide another email

    normalized = invoice.model_dump(mode="json")
    normalized["paymentLinks"] = [_bare(u) for u in invoice.paymentLinks or []] or None
    own = db.scalar(select(InvoiceEmail.row_id).where(InvoiceEmail.message_key == key))
    duplicate = own is not None
    if not duplicate:
        db.add(InvoiceEmail(
            message_key=key, invoice_id=invoice.id, kind=mail["kind"], template=mail["template"],
            normalized=normalized, links=_links(mail), received_at=datetime.utcnow(),
        ))
        try:
            db.commit()
        except IntegrityError:  # the same email arrived twice at once
            db.rollback()
            duplicate = True
        own = db.scalar(select(InvoiceEmail.row_id).where(InvoiceEmail.message_key == key))

    # Judged against the email that came right before this one's own stored copy. A duplicate is judged again with
    # today's rules instead of handing back the stored verdict, which would keep showing what older rules concluded.
    previous = db.scalars(
        select(InvoiceEmail).where(InvoiceEmail.invoice_id == invoice.id, InvoiceEmail.row_id < own)
        .order_by(InvoiceEmail.row_id.desc()).limit(1)
    ).first()
    extra = assess_email(mail, normalized, previous.normalized if previous else None)
    check = await run_check(db, invoice.id, legacy_invoice(invoice), use_ai=ai, extra=extra, normalized=invoice)
    return {
        "stored": not duplicate, "duplicate": duplicate, "kind": mail["kind"], "template": mail["template"],
        "invoiceId": invoice.id, "invoice": normalized, "links": _links(mail), "check": check,
    }

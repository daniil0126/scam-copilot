import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app import llm
from app.db import get_db
from app.email_rules import page_findings
from app.models import Check, InvoiceEmail
from app.normalize import Invoice, normalize_paypal, normalize_payer_page
from app.payer_page import MAX_TEXT, is_payer_page
from app.paypal import fetch_invoices, get_invoice, valid_invoice_id
from app.scoring import apply_extra, score_invoice
from app.vendor_history import build_vendor_history

router = APIRouter(prefix="/checks", tags=["checks"])

# A2: RULES_ENGINE=v2 switches to the rule engine (app/rules/engine.py). Anything else keeps the legacy scorer,
# so the flag can be flipped back without a deploy and existing tests stay green. Read on every call, not at import,
# so tests can switch it per test with monkeypatch.setenv.
def _rules_engine_v2() -> bool:
    import os
    return os.getenv("RULES_ENGINE", "v1").strip().lower() == "v2"


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


# --- A2: adapters between normalize.Invoice and rules.types.Invoice ---------------------------------------------

def to_rules_invoice(inv: Invoice) -> "rules_invoice":
    """Maps `app.normalize.Invoice` to `app.rules.types.Invoice`. The two models share field names; only `items`
    are a different class and are rebuilt here. `source` accepts "email" since the rule engine's Literal was widened."""
    from app.rules.types import Invoice as RulesInvoice, InvoiceItem as RulesItem

    items = [RulesItem(**i.model_dump()) for i in inv.items] if inv.items else None
    return RulesInvoice(
        id=inv.id,
        accountId=inv.accountId,
        source=inv.source,
        invoiceNumber=inv.invoiceNumber,
        status=inv.status,
        amount=inv.amount,
        currency=inv.currency,
        invoiceDate=inv.invoiceDate,
        dueDate=inv.dueDate,
        senderName=inv.senderName,
        senderLegalName=inv.senderLegalName,
        senderEmail=inv.senderEmail,
        senderPhone=inv.senderPhone,
        recipientName=inv.recipientName,
        recipientEmail=inv.recipientEmail,
        paymentTerms=inv.paymentTerms,
        items=items,
        paymentLinks=inv.paymentLinks,
        note=inv.note,
        createdAt=inv.createdAt,
        updatedAt=inv.updatedAt,
        contentHash=inv.contentHash,
    )


# Reverse of notifications/categories.LEGACY_TYPES, so a v2 signal also shows up under the legacy `id` that
# scoring.apply_extra and llm.build_context read. New signal types (duplicates, activity) have no legacy id and
# are only visible through the contract form.
# Legacy `id` and `label` per contract signal type. The label is the exact string `scoring.score_invoice` writes
# today, so that an alert, a report or the extension sees the same words under v1 and v2. A signal type without a
# legacy counterpart (duplicates, activity) falls back to a readable label built from the type; nothing that reads
# the legacy form needs to know the difference, and the contract form is still in `result["signals"]`.
_LEGACY_FINDING: dict[str, tuple[str, str]] = {
    "SENDER_MISMATCH": ("payee", "Payment email changed"),
    "SENDER_NAME_CHANGED": ("supplier", "Supplier name changed"),
    "NEW_SENDER": ("supplier", "New supplier"),
    "UNUSUAL_AMOUNT": ("amount", "Amount far from usual"),
    "SUSPICIOUS_LINK": ("link", "Link in invoice text"),
    "PHONE_IN_TEXT": ("phone", "Phone number in invoice text"),
    "SCAM_WORDING": ("wording", "Suspicious wording"),
    "BRAND_IMPERSONATION": ("brand", "Possible brand impersonation"),
    "DUE_DATE_ISSUE": ("due", "Due date issue"),
    "DUPLICATE_EXACT": ("duplicate", "Exact duplicate"),
    "DUPLICATE_POTENTIAL": ("duplicate", "Possible duplicate"),
    "DUPLICATE_SIMILAR": ("duplicate", "Similar to an earlier invoice"),
    "UNUSUAL_SENDER_ACTIVITY": ("activity", "Unusual sender activity"),
}

_SEVERITY_TO_LEGACY = {"LOW": "low", "MEDIUM": "medium", "HIGH": "high", "CRITICAL": "high"}
_LEVEL_TO_LEGACY = {"LOW": "low", "MEDIUM": "medium", "HIGH": "high", "CRITICAL": "high"}


def risk_to_legacy(risk, invoice_flat: dict) -> dict:
    """Builds the result that the rest of the product reads, from a `rules.types.RiskResult`.

    The dict carries both shapes at once:
    - legacy keys (`level`, `score`, `findings`, `comparison`, `recommendation`, `evidence`, `invoice`) — what
      `scoring.apply_extra`, `llm.build_context` and the frontend already know. `id` and `label` match the strings
      `scoring.score_invoice` writes, so an alert or a test that reads them sees no difference between v1 and v2;
    - contract keys (`riskLevel`, `riskScore`, `signals`, `confidence`, `engineVersion`, `analyzedAt`) — what
      `notifications/categories.py` and `reports/service.py` read when "signals" is present.

    CRITICAL is passed on as legacy `high` with a score of 80 or more, which is how `categories.risk_level` recovers
    it. A DETECTED signal becomes a finding; INSUFFICIENT_DATA becomes a skipped finding so `categories.detected`
    leaves it out (same convention as email_rules._finding(..., skipped=True)).
    """
    findings: list[dict] = []
    evidence: list[str] = []
    for s in risk.signals:
        legacy_id, legacy_label = _LEGACY_FINDING.get(
            s.type, (s.type.lower(), s.type.replace("_", " ").capitalize())
        )
        severity = _SEVERITY_TO_LEGACY[s.severity]
        if s.status == "DETECTED":
            findings.append({"id": legacy_id, "label": legacy_label, "severity": severity, "detail": s.evidence})
            evidence.append(s.evidence)
        else:
            findings.append({"id": legacy_id, "label": legacy_label, "severity": "ok",
                             "detail": s.evidence or "not checked", "skipped": True})

    legacy_level = _LEVEL_TO_LEGACY[risk.riskLevel]
    score = risk.riskScore
    if risk.riskLevel == "CRITICAL":
        score = max(score, 80)

    legacy_comparison = [
        {"field": row.field, "current": row.current, "previous": row.previous, "differs": row.differs}
        for row in risk.comparison
    ]
    recommendation = (
        risk.recommendations[0]
        if risk.recommendations
        else ("No obvious issues were found. Pay only through your usual, trusted channels."
              if risk.riskLevel == "LOW"
              else "Some details look unusual. Verify them with the supplier before paying.")
    )

    return {
        # legacy form
        "level": legacy_level,
        "score": score,
        "findings": findings,
        "comparison": legacy_comparison,
        "recommendation": recommendation,
        "evidence": evidence,
        "invoice": invoice_flat,
        # contract form (read by notifications/categories.py and reports/service.py)
        "riskLevel": risk.riskLevel,
        "riskScore": risk.riskScore,
        "confidence": risk.confidence,
        "signals": [s.model_dump() for s in risk.signals],
        "engineVersion": risk.engineVersion,
        "analyzedAt": risk.analyzedAt.isoformat(),
    }


def _recompute_contract_after_extra(result: dict) -> None:
    """`scoring.apply_extra` rewrites legacy level/score/findings; mirror that onto the contract keys so that
    notifications and reports do not see a stale view after email or page findings were added.

    `categories.risk_level` trusts a `riskLevel` already present in the dict, so it is removed first: the legacy
    fields are the source of truth here, and CRITICAL is recovered from legacy `high` with a score of 80 or more.
    """
    from app.notifications import categories

    legacy = {k: v for k, v in result.items() if k not in ("riskLevel", "riskScore")}
    result["riskLevel"] = categories.risk_level(legacy)
    result["riskScore"] = categories.risk_score(legacy)


# --- the check pipeline -----------------------------------------------------------------------------------------

async def run_check(
    db: Session, invoice_id: str, invoice: dict, ignore: frozenset[str] = frozenset(), use_ai: bool = False,
    extra: dict | None = None, normalized: Invoice | None = None,
) -> dict:
    """Scores an already loaded invoice against the history and stores the result.

    `ignore` lists PayPal invoice ids that must not serve as history (used by the bulk run).
    `use_ai` adds the LLM review (a no-op when no provider is configured).
    `extra` carries findings from another source (see `scoring.apply_extra`), added before the AI review and the save.
    `normalized` is the contract `Invoice` the caller already holds (PayPal detail, payer page or email). When
    RULES_ENGINE=v2 and `normalized` is given, the rule engine runs on `normalized` and `build_vendor_history`;
    otherwise the legacy scorer is used with `invoice`.
    """
    supplier = invoice["supplier"]

    existing = db.scalars(select(Check).where(Check.paypal_invoice_id == invoice_id)).first()

    now = datetime.now(timezone.utc).replace(tzinfo=None)  # stored naive UTC, as before

    if _rules_engine_v2() and normalized is not None:
        from app.monitor import account_id as _account_id
        from app.rules.engine import evaluate as _evaluate
        from app.rules.config import RulesConfig
        from app.rules.types import VendorHistory

        rules_invoice = to_rules_invoice(normalized)
        history = VendorHistory.model_validate(build_vendor_history(db, _account_id(), normalized))
        risk = _evaluate(rules_invoice, history, RulesConfig())
        result = {
            "id": existing.id if existing else str(uuid.uuid4()),
            "invoice": invoice,
            "checkedAt": now.isoformat(timespec="seconds") + "Z",
            **risk_to_legacy(risk, invoice),
        }
    else:
        # History to compare with: other invoices only, never the invoice being checked.
        latest = (
            select(Check).where(Check.paypal_invoice_id.not_in(ignore | {invoice_id}))
            .order_by(desc(Check.checked_at)).limit(1)
        )
        # A blank name or email is "not shown", not a supplier: matching on it would "confirm" one unknown against another.
        previous = db.scalars(latest.where(Check.supplier_name == supplier["name"])).first() if supplier["name"] else None
        known_by_email = (
            db.scalars(latest.where(Check.supplier_email == supplier["email"])).first() if supplier["email"] else None
        )
        result = {
            "id": existing.id if existing else str(uuid.uuid4()),
            "invoice": invoice,
            "checkedAt": now.isoformat(timespec="seconds") + "Z",
            **score_invoice(invoice, previous, known_by_email),
        }

    if extra:
        apply_extra(result, extra)
        if "riskLevel" in result:  # v2 result: keep the contract view in sync with the legacy one
            _recompute_contract_after_extra(result)
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
    """Rules only, so the answer is quick; the AI explanation is a separate call (`POST /checks/{id}/explain`)."""
    invoice_id = valid_invoice_id(body.invoice_id)  # A5: the id goes into a PayPal URL
    flat = await get_invoice(invoice_id)  # legacy flat shape from to_invoice()
    # A2: for the rule engine we need the contract Invoice too. `get_invoice` already fetched the invoice, but it
    # returns only the flat view; when v2 is on, fetch the same resource once more to normalize it. Tests that
    # replace `get_invoice` do not replace `paypal_request`, so a failure here falls back to the legacy path
    # instead of breaking the endpoint. The monitor passes `normalized` directly and never takes this path.
    normalized = None
    if _rules_engine_v2():
        try:
            from app.paypal import paypal_request
            raw = await paypal_request("GET", f"/v2/invoicing/invoices/{invoice_id}")
            normalized = normalize_paypal(raw)
        except Exception as e:
            llm.log.warning("normalize_paypal failed for %s, falling back to legacy: %s", invoice_id, type(e).__name__)
    return await run_check(db, invoice_id, flat, normalized=normalized)


@router.post("/{check_id}/explain")
async def explain_check(check_id: str, db: Session = Depends(get_db)):
    """Adds the AI explanation to a stored check and returns the whole result. It can take as long as the model does
    (up to LLM_TIMEOUT_SECONDS), which is why a check does not wait for it. A check that already has one, or that AI is
    off or not needed for (a LOW result), comes back unchanged."""
    check = db.get(Check, check_id)
    if check is None:
        raise HTTPException(404, "Check not found.")
    result = dict(check.result)
    if "ai" not in result and (analysis := await llm.analyse_invoice(result["invoice"], result)):
        llm.apply_analysis(result, analysis)
        check.result = result  # a new dict: an in-place change would not be seen as one
        db.commit()
    return result


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
    return await run_check(db, inv.id, legacy_invoice(inv), extra=extra, normalized=inv)


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
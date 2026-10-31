"""Risk findings that only an invoice email can give: where its links lead, and what changed since the earlier email.

Returns the `extra` dict of `scoring.apply_extra`. Nothing here guesses: a field the email does not show (the seller's
note in an update email) is never compared, and a missing earlier email is reported as "cannot compare", not as safe.
The seller's note in an update email is a blind spot of PayPal's emails, not of this code: it is read from the payment
page, which is a separate check.

Emails are compared in the order they arrived. If an update email arrives before the first one, the comparison runs the
wrong way round; PayPal sends the first one at least a little earlier, so this is rare, and not handled.
"""
import re
from decimal import Decimal

# Links whose text invites a click. Footer and social links lead outside PayPal in real emails and are not judged.
CALL_TO_ACTION = re.compile(r"\b(pay|invoice|view|details|confirm|verify|review|click|login|log in|sign in)\b", re.IGNORECASE)


def _finding(fid, label, severity, pts, text, skipped=False):
    """`skipped` marks a check that could not run: it is neither a pass nor a risk, and the panel shows it apart."""
    return {"id": fid, "label": label, "severity": severity, "pts": pts, "text": text, **({"skipped": True} if skipped else {})}


def _money(value) -> str:
    return f"{Decimal(str(value)):.2f}"


def link_findings(mail: dict) -> list[dict]:
    out = []
    primary = mail["primaryLink"]
    if primary and not primary["isPaypal"]:
        where = primary["host"] or "an address that is not a plain https link"
        out.append(_finding("email-link", "Payment link does not lead to PayPal", "high", 60,
                            f"The button in this email opens {where}, not paypal.com. Do not click it."))
    for link in mail["links"]:
        if link is primary:
            continue
        if link["textMismatch"]:
            out.append(_finding("email-link-text", "A link shows one address but opens another", "high", 40,
                                f"The link reads \"{link['text'][:60]}\" but opens {link['host'] or 'an unsafe address'}."))
        elif not link["isPaypal"] and CALL_TO_ACTION.search(link["text"]):
            out.append(_finding("email-link-other", "Another link leads outside PayPal", "medium", 25,
                                f"The link \"{link['text'][:60]}\" opens {link['host'] or 'an unsafe address'}."))
    return out


def change_findings(mail: dict, invoice: dict, previous: dict | None) -> tuple[list[dict], list[dict]]:
    """Compares this email with the earlier email of the same invoice. `invoice` and `previous` are normalized invoices."""
    if mail["kind"] != "updated":
        return [], []
    if previous is None:
        return [_finding("email-change", "Changes not checked: no earlier email", "ok", 0,
                         "PayPal says this invoice was updated, but the first email is not here, so changes cannot be shown.",
                         skipped=True)], []

    findings, rows = [], []
    amount, before = invoice.get("amount"), previous.get("amount")
    changed_visible = False
    if amount is not None and before is not None:
        old, new = Decimal(before), Decimal(amount)
        rows.append({"field": "Amount (earlier email)", "current": f"{_money(new)} {invoice.get('currency') or ''}".strip(),
                     "previous": f"{_money(old)} {previous.get('currency') or ''}".strip(), "differs": old != new})
        if invoice.get("currency") and previous.get("currency") and invoice["currency"] != previous["currency"]:
            changed_visible = True
            findings.append(_finding("email-currency", "Currency changed after sending", "high", 40,
                                     f"The invoice was in {previous['currency']} and is now in {invoice['currency']}."))
        elif old != new:
            changed_visible = True
            if old > 0:
                change = (new - old) / old
                if change > 1:
                    findings.append(_finding("email-amount", "Amount raised sharply after sending", "high", 40,
                                             f"The total went from {_money(old)} to {_money(new)} ({change:+.0%}) after the invoice was sent."))
                elif change > Decimal("0.25"):
                    findings.append(_finding("email-amount", "Amount raised after sending", "medium", 25,
                                             f"The total went from {_money(old)} to {_money(new)} ({change:+.0%}) after the invoice was sent."))
    due, due_before = invoice.get("dueDate"), previous.get("dueDate")
    if due and due_before:
        rows.append({"field": "Due date (earlier email)", "current": due, "previous": due_before, "differs": due != due_before})
        if due != due_before:
            changed_visible = True
            if due < due_before:  # ISO dates compare as text
                findings.append(_finding("email-due", "Due date moved earlier", "medium", 20,
                                         f"The due date went from {due_before} to {due}: less time to check before paying."))
    names, names_before = [i.get("name") for i in invoice.get("items") or []], [i.get("name") for i in previous.get("items") or []]
    if names and names_before and names != names_before:
        changed_visible = True
        findings.append(_finding("email-items", "Items changed after sending", "medium", 20,
                                 f"The items went from {', '.join(map(str, names_before))} to {', '.join(map(str, names))}."))

    comparable = amount is not None and before is not None and bool(due and due_before) and bool(names and names_before)
    if not changed_visible and comparable:
        findings.append(_finding("email-silent", "Updated, but nothing visible changed", "medium", 25,
                                 "PayPal says the invoice was updated, yet the amount, due date and items in the email are the same. "
                                 "What changed is not shown in the email; it is often the seller's note. Open the payment page and read it."))
    return findings, rows


def assess_email(mail: dict, invoice: dict, previous: dict | None) -> dict:
    changes, rows = change_findings(mail, invoice, previous)
    return {"findings": [*link_findings(mail), *changes], "comparison": rows}


def _same_text(a: str, b: str) -> bool:
    return " ".join(a.split()) == " ".join(b.split())


def _short(text: str, limit: int = 120) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def page_findings(page: dict, emails: list[dict]) -> dict:
    """Compares the payment page the user is about to pay on with the emails PayPal sent about the same invoice.

    `page` is the normalized payer page, `emails` the normalized emails of that invoice in the order they arrived. The page
    is always current, so any difference from the last email means the invoice changed without the email showing it, and
    the note (which update emails leave out) is only comparable with the last email that showed one. A field either side
    does not show is skipped. With no email there is nothing to compare and nothing is returned.
    """
    if not emails:
        return {"findings": [], "comparison": []}
    last, findings, rows = emails[-1], [], []
    compared = False

    amount, was = page.get("amount"), last.get("amount")
    if amount is not None and was is not None:
        compared = True
        rows.append({"field": "Amount (page vs email)", "current": f"{_money(amount)} {page.get('currency') or ''}".strip(),
                     "previous": f"{_money(was)} {last.get('currency') or ''}".strip(), "differs": Decimal(amount) != Decimal(was)})
        if page.get("currency") and last.get("currency") and page["currency"] != last["currency"]:
            findings.append(_finding("page-currency", "Page currency differs from the email", "high", 40,
                                     f"The page is in {page['currency']}, the last email was in {last['currency']}."))
        elif Decimal(amount) != Decimal(was):
            findings.append(_finding("page-amount", "Page amount differs from the last email", "high", 40,
                                     f"The page asks {_money(amount)}, but the last email said {_money(was)}."))
    due, due_was = page.get("dueDate"), last.get("dueDate")
    if due and due_was:
        compared = True
        rows.append({"field": "Due date (page vs email)", "current": due, "previous": due_was, "differs": due != due_was})
        if due != due_was:
            findings.append(_finding("page-due", "Page due date differs from the last email", "medium", 20,
                                     f"The page says {due}, the last email said {due_was}."))
    names = [i.get("name") for i in page.get("items") or []]
    names_was = [i.get("name") for i in last.get("items") or []]
    if names and names_was:
        compared = True
        if names != names_was:
            findings.append(_finding("page-items", "Page items differ from the last email", "medium", 20,
                                     f"The page lists {', '.join(map(str, names))}; the last email listed {', '.join(map(str, names_was))}."))

    page_note = page.get("note")
    noted = next((e for e in reversed(emails) if e.get("note") is not None), None)
    if noted and page_note:
        compared = True
        differs = not _same_text(page_note, noted["note"])
        rows.append({"field": "Seller's note (page vs email)", "current": _short(page_note), "previous": _short(noted["note"]), "differs": differs})
        if differs:
            findings.append(_finding("page-note", "Seller's note changed after the email", "medium", 25,
                                     f"The email showed \"{_short(noted['note'])}\", the page now shows \"{_short(page_note)}\"."))
    elif noted is None and page_note and any(e.get("kind") == "new" for e in emails):
        compared = True
        findings.append(_finding("page-note-new", "Page has a note the first email did not show", "medium", 15,
                                 f"The first email showed no note, but the page shows \"{_short(page_note)}\". It may have been added after the invoice was sent."))

    if compared and not findings:
        findings.append(_finding("page-match", "Page matches the emails", "ok", 0,
                                 "The amount, due date, items and note on the page are the same as in the emails PayPal sent."))
    return {"findings": findings, "comparison": rows}

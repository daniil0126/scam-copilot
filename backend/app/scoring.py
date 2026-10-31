import re
from datetime import date

from app.models import Check

PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
LINK_RE = re.compile(r"https?://|www\.", re.I)
SCAM_WORDS = ("cancel", "refund", "call us", "call now", "unauthorized", "unauthorised", "suspicious",
              "renewed", "auto-renew", "subscription", "charged", "dispute", "helpline", "support number")
BRANDS = ("norton", "mcafee", "geek squad", "geeksquad", "lifelock", "avast", "amazon", "apple", "microsoft",
          "paypal", "best buy", "walmart", "netflix")


RECOMMENDATIONS = {
    "high": "This invoice differs from previous ones. Contact the supplier through an official channel before paying.",
    "medium": "Some details look unusual. Verify them with the supplier before paying.",
    "low": "No obvious issues were found. Pay only through your usual, trusted channels.",
}


def level_for(score: int, findings: list[dict]) -> str:
    level = "high" if score >= 60 else "medium" if score >= 30 else "low"
    if level == "low" and any(f["severity"] == "high" for f in findings):
        level = "medium"  # one serious red flag is never "low risk"
    return level


def apply_extra(result: dict, extra: dict) -> None:
    """Adds findings from another source (the email rules) to a scored result and recomputes score and level.

    `extra` is {"findings": [{id, label, severity, pts, text}], "comparison": [rows]}.
    """
    for f in extra.get("findings", []):
        result["findings"].append({
            "id": f["id"], "label": f["label"], "severity": f["severity"], "detail": f["text"],
            **({"skipped": True} if f.get("skipped") else {}),
        })
        result["evidence"].append(f["text"])
        result["score"] = min(result["score"] + f["pts"], 100)
    result["comparison"] = [*result["comparison"], *extra.get("comparison", [])]
    result["level"] = level_for(result["score"], result["findings"])
    result["recommendation"] = RECOMMENDATIONS[result["level"]]


def score_invoice(invoice: dict, previous: Check | None, known_by_email: Check | None):
    supplier = invoice["supplier"]
    findings, evidence, comparison, points = [], [], [], 0

    def add(fid, label, severity, pts, text):
        nonlocal points
        findings.append({"id": fid, "label": label, "severity": severity, "detail": text})
        evidence.append(text)
        points += pts

    if previous is None and known_by_email is None:
        add("supplier", "New supplier", "medium", 15, "This supplier has no earlier checks in your history.")
    else:
        prev = previous or known_by_email
        if previous and previous.supplier_email and supplier["email"] and previous.supplier_email != supplier["email"]:
            add("payee", "Payment email changed", "high", 60,
                "The PayPal account receiving the payment differs from the one on the previous invoice.")
        elif known_by_email and not previous:
            add("supplier", "Supplier name changed", "medium", 40,
                f"This PayPal account was earlier used under the name \"{known_by_email.supplier_name}\".")
        else:
            add("supplier", "Supplier confirmed", "ok", 0, "The supplier matches an earlier check.")

        if prev.amount > 0:
            change = (invoice["amount"] - prev.amount) / prev.amount
            if abs(change) > 1:
                add("amount", "Amount far from usual", "high", 25,
                    f"The total differs by {change:+.0%} from the previous invoice.")
            elif abs(change) > 0.25:
                add("amount", "Amount mismatch", "medium", 15,
                    f"The total differs by {change:+.0%} from the previous invoice.")
            else:
                add("amount", "Amount within normal range", "ok", 0, "The total is close to the previous invoice.")

        comparison = [
            {"field": "Supplier", "current": supplier["name"], "previous": prev.supplier_name,
             "differs": bool(supplier["name"] and prev.supplier_name) and supplier["name"] != prev.supplier_name},
            {"field": "PayPal email", "current": supplier["email"], "previous": prev.supplier_email,
             "differs": bool(supplier["email"] and prev.supplier_email) and supplier["email"] != prev.supplier_email},
            {"field": "Amount", "current": f"{invoice['amount']:.2f} {invoice['currency']}",
             "previous": f"{prev.amount:.2f} {prev.currency}", "differs": invoice["amount"] != prev.amount},
        ]

    text = invoice.get("note", "")
    lowered = text.lower()
    if PHONE_RE.search(text):
        add("phone", "Phone number in invoice text", "high", 35,
            "The invoice text contains a phone number. Fake invoices often ask you to call to \"cancel\" or \"dispute\" a charge.")
    if LINK_RE.search(text):
        add("link", "Link in invoice text", "medium", 15, "The invoice text contains a web link.")
    hits = [w for w in SCAM_WORDS if w in lowered]
    if hits:
        add("wording", "Suspicious wording", "medium", 20, f"The invoice text uses typical scam wording: {', '.join(hits[:3])}.")
    name_l = supplier["name"].lower()
    domain = supplier["email"].split("@")[-1].lower() if supplier["email"] else ""
    for brand in BRANDS:
        if brand in name_l and brand.replace(" ", "") not in domain:
            add("brand", f"Possible {brand.title()} impersonation", "high", 40,
                f"The sender is named \"{supplier['name']}\" but their PayPal email"
                f"{' (' + supplier['email'] + ')' if supplier['email'] else ''} does not belong to that brand.")
            break
    if previous is None and known_by_email is None and invoice["amount"] >= 300:
        add("amount_new", "Large amount from unknown sender", "medium", 15,
            f"A first-time sender is asking for {invoice['amount']:.2f} {invoice['currency']}.")

    due = invoice["dueDate"]
    if not due:
        add("due", "No due date", "medium", 10, "The invoice has no due date, which is unusual for a real supplier.")
    elif date.fromisoformat(due) < date.today():
        add("due", "Overdue invoice", "medium", 10, "The due date is already in the past; scammers often add urgency.")

    score = min(points, 100)
    level = level_for(score, findings)
    return {"level": level, "score": score, "findings": findings, "comparison": comparison,
            "recommendation": RECOMMENDATIONS[level], "evidence": evidence}

"""Reads the text of a PayPal payer page (`/invoice/p/#...`) into invoice fields.

Built only on pages seen in the Sandbox (tests/fixtures/payer_pages). Anything the page does not show stays None;
nothing is guessed. Not seen yet, so not handled: other currencies than USD in symbol form, invoices with
discounts or tax lines, paid or cancelled invoices (their labels may differ), non-English pages.
"""
import re
from datetime import date
from decimal import Decimal
from urllib.parse import urlparse

EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MONEY = re.compile(r"^(-?\d[\d,]*(?:\.\d+)?)\s+(\S+)$")
LINE_ITEM = re.compile(r"^(\d[\d,.]*)\s+x\s+(\d[\d,]*(?:\.\d+)?)\s+(\S+)$")
ISSUED = re.compile(r"^Issued:\s*(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})$")
DUE_BY = re.compile(r"^Due by\s+(\d{1,2})/(\d{1,2})/(\d{4})$")
DBA = re.compile(r"Invoice issued by (.+?) \(doing business as (.+?)\)")
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
CURRENCIES = {"US$": "USD"}  # only what has been seen; a bare ISO code is accepted as is
SECTIONS = {"Bill to", "Note from seller", "Items", "Subtotal", "Total", "Amount due"}
MAX_TEXT = 20_000


def is_payer_page(url: str, text: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = parsed.hostname or ""
    on_paypal = host == "paypal.com" or host.endswith(".paypal.com")
    return on_paypal and parsed.path.startswith("/invoice/p/") and "Amount due" in text and "Report invoice" in text


def invoice_id_from_url(url: str) -> str | None:
    """The page keeps the invoice id in the hash without the prefix and dashes: #5BEXVJZWMSZMJRVQ."""
    short = re.fullmatch(r"#?([A-Z0-9]{16})", urlparse(url).fragment or "")
    return "INV2-" + "-".join(re.findall(".{4}", short.group(1))) if short else None


def _currency(token: str) -> str | None:
    return CURRENCIES.get(token) or (token if re.fullmatch(r"[A-Z]{3}", token) else None)


def _amount(value: str) -> Decimal:
    return Decimal(value.replace(",", ""))


def _due(line: str) -> date | None:
    m = DUE_BY.match(line)
    if not m:
        return None
    a, b, year = int(m[1]), int(m[2]), int(m[3])
    try:
        if a > 12 or a == b:
            return date(year, b, a)  # day/month
        if b > 12:
            return date(year, a, b)  # month/day
    except ValueError:
        pass
    return None  # both parts <= 12 and different: the page does not say which is the day


def parse_payer_page(text: str) -> dict:
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    out: dict = {
        "number": None, "displayName": None, "legalName": None, "senderEmail": None, "address": None,
        "amount": None, "currency": None, "issued": None, "dueText": None, "dueDate": None,
        "recipientEmail": None, "recipientName": None, "note": None, "items": None,
    }
    head = next((i for i, ln in enumerate(lines) if ln.startswith("Invoice #")), None)
    if head is None:
        return out
    out["number"] = lines[head][len("Invoice #"):].strip() or None

    first_money = next((i for i in range(head + 1, len(lines)) if MONEY.match(lines[i])), None)
    if first_money is not None:
        m = MONEY.match(lines[first_money])
        out["amount"], out["currency"] = _amount(m[1]), _currency(m[2])
        block = lines[head + 1:first_money]
        if block:
            out["displayName"] = block[0]
            out["senderEmail"] = next((b.lower() for b in block[1:] if EMAIL.match(b)), None)
            address = [b for b in block[1:] if not EMAIL.match(b)]
            out["address"] = ", ".join(address) or None
        for ln in lines[first_money + 1:first_money + 4]:
            if (m := ISSUED.match(ln)) and m[2].lower() in MONTHS:
                try:
                    out["issued"] = date(int(m[3]), MONTHS[m[2].lower()], int(m[1]))
                except ValueError:
                    pass
            elif ln.startswith("Due "):
                out["dueText"], out["dueDate"] = ln, _due(ln)

    def section(title: str, stop: set[str]) -> list[str]:
        if title not in lines:
            return []
        start = lines.index(title) + 1
        end = next((i for i in range(start, len(lines)) if lines[i] in stop), len(lines))
        return lines[start:end]

    bill = section("Bill to", SECTIONS - {"Bill to"})
    out["recipientEmail"] = next((b.lower() for b in bill if EMAIL.match(b)), None)
    out["recipientName"] = next((b for b in bill if not EMAIL.match(b)), None)
    out["note"] = "\n".join(section("Note from seller", SECTIONS - {"Note from seller"})) or None

    items: list[dict] = []
    for ln in section("Items", {"Subtotal", "Total", "Amount due"}):
        if m := LINE_ITEM.match(ln):
            if items:
                items[-1].update(quantity=m[1], unitAmount=m[2].replace(",", ""))
        elif MONEY.match(ln):
            if items:
                items[-1]["_priced"] = True  # the line total, derived from quantity and unit amount
        elif items and items[-1]["description"] is None and not items[-1].get("_priced"):
            items[-1]["description"] = ln  # a second text line before the price (layout not seen yet)
        else:
            items.append({"name": ln, "description": None, "quantity": None, "unitAmount": None})
    for it in items:
        it.pop("_priced", None)
    out["items"] = items or None

    if m := DBA.search(text):
        out["legalName"], out["displayName"] = m[1].strip(), m[2].strip()
    return out

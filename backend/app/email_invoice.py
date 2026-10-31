"""Reads a PayPal invoice notification email (the HTML of the message sent to the payer) into invoice fields.

Built only on sandbox emails seen so far (tests/fixtures/emails): "Invoice from X" and "X updated your invoice". Anything
the email does not show stays None, nothing is guessed. In particular the update email does not carry the seller's note,
so a missing note there means "not shown", never "removed". Not seen yet, so not handled: other currencies than USD in
symbol form, discounts, tax lines, dates in other formats, reminders, receipts, non-English emails.

The email is attacker-controlled input: the HTML is only parsed, never rendered, and every link is judged by its real
host (`link_is_paypal`), not by the text shown next to it.
"""
import re
from datetime import date
from decimal import Decimal
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

MAX_HTML = 500_000
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
HEAD_MONEY = re.compile(r"^\$(\d[\d,]*(?:\.\d{2})?)\s+([A-Z]{3})$")
PLAIN_MONEY = re.compile(r"^\$\d[\d,]*(?:\.\d{2})?$")
LINE_ITEM = re.compile(r"^(\d[\d,.]*)\s+x\s+\$(\d[\d,]*(?:\.\d{2})?)$")
DUE_ON = re.compile(r"^Due on ([A-Za-z]{3})[a-z]* (\d{1,2}), (\d{4})$")
TITLE_NEW = re.compile(r"^Invoice from (.+) \(([^()]+)\)$")
TITLE_UPDATED = re.compile(r"^(.+) updated your invoice \(([^()]+)\)$")
INVOICE_ID = re.compile(r"/(INV2-[A-Z0-9]{4}(?:-[A-Z0-9]{4}){3})(?:[/?#]|$)")
TEMPLATE = re.compile(r"\b(RTI?\d{6}):")
LOOKS_LIKE_URL = re.compile(r"^(?:https?://)?[\w-]+(?:\.[\w-]+)+(?:[/?#]\S*)?$", re.IGNORECASE)
KINDS = {"invoice-buyer-notification": "new", "invoice-buyer-updated": "updated"}


def _same_site(shown_host: str | None, real_host: str) -> bool:
    """True when the link opens the address its text shows, or a subdomain of it ("PayPal.com" -> www.paypal.com).

    The other way round is a mismatch, and so is `paypal.com.evil.example`: it is not a subdomain of paypal.com.
    """
    if not shown_host:
        return False
    shown = shown_host.removeprefix("www.")
    real = real_host.removeprefix("www.")
    return real == shown or real.endswith("." + shown)


def link_host(url: str) -> str | None:
    """The host a browser would open, or None for anything that is not a plain https link with no tricks.

    Rejected on purpose: other schemes, a user-info part (`https://paypal.com@evil.example`), backslashes and control
    characters (browsers read `\\` as `/`, so the host differs from what urlparse sees).
    """
    url = (url or "").strip()
    if not url or "\\" in url or any(ord(c) <= 32 or ord(c) == 127 for c in url):
        return None
    try:
        parsed = urlparse(url)
        host = parsed.hostname
    except ValueError:
        return None
    if parsed.scheme != "https" or not host or "@" in parsed.netloc:
        return None
    return host.lower().rstrip(".")


def link_is_paypal(url: str) -> bool:
    host = link_host(url)
    return bool(host) and (host == "paypal.com" or host.endswith(".paypal.com"))


class _Reader(HTMLParser):
    """Collects the visible text nodes, the links and the title. Hidden elements (the pre-header) are skipped."""

    def __init__(self):
        super().__init__()
        self.lines: list[str] = []
        self.links: list[dict] = []
        self.title = ""
        self._in_title = False
        self._skip: str | None = None  # tag name of the hidden or non-visible element being skipped
        self._depth = 0
        self._anchor: dict | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self._skip:
            self._depth += tag == self._skip
            return
        if tag in ("style", "script") or "display:none" in (a.get("style") or "").replace(" ", "").lower():
            self._skip, self._depth = tag, 1
            return
        if tag == "title":
            self._in_title = True
        elif tag == "a" and a.get("href"):
            self._anchor = {"url": a["href"].strip(), "text": ""}

    def handle_endtag(self, tag):
        if self._skip:
            if tag == self._skip:
                self._depth -= 1
                if self._depth == 0:
                    self._skip = None
            return
        if tag == "title":
            self._in_title = False
        elif tag == "a" and self._anchor:
            self.links.append(self._anchor)
            self._anchor = None

    def handle_data(self, data):
        if self._skip:
            return
        text = " ".join(data.split())  # also turns &nbsp; into a plain space
        if not text:
            return
        if self._in_title:
            self.title = text
            return
        self.lines.append(text)
        if self._anchor is not None:
            self._anchor["text"] = (self._anchor["text"] + " " + text).strip()


def _month_day_year(line: str) -> date | None:
    m = DUE_ON.match(line)
    if not m or m[1].lower() not in MONTHS:
        return None
    try:
        return date(int(m[3]), MONTHS[m[1].lower()], int(m[2]))
    except ValueError:
        return None


def parse_invoice_email(html: str) -> dict:
    if len(html) > MAX_HTML:
        raise ValueError("email is too large")
    reader = _Reader()
    reader.feed(html)
    reader.close()
    lines = reader.lines

    out: dict = {
        "kind": "unknown", "template": None, "number": None, "merchant": None, "invoiceId": None,
        "amount": None, "currency": None, "dueDate": None, "note": None, "items": None,
        "recipientEmail": None, "recipientName": None, "primaryLink": None, "links": [],
    }
    for ln in lines:
        if m := TEMPLATE.search(ln):
            out["template"] = m[1]

    links = []
    for link in reader.links:
        host = link_host(link["url"])
        shown = link["text"]
        links.append({
            "url": link["url"], "text": shown, "host": host, "isPaypal": link_is_paypal(link["url"]),
            # the text reads like an address but leads somewhere else
            "textMismatch": bool(LOOKS_LIKE_URL.match(shown)) and host is not None
            and not _same_site(link_host(shown if shown.lower().startswith("http") else "https://" + shown), host),
        })
    out["links"] = links
    primary = next((l for l in links if re.search(r"\bview\b.*\binvoice\b", l["text"], re.IGNORECASE)), None)
    out["primaryLink"] = primary

    if any(ln.startswith("We sent your ") for ln in lines):
        out["kind"] = "issuer_copy"  # the confirmation PayPal sends to the issuer, not a notice for the payer
        return out

    tpcid = (parse_qs(urlparse(primary["url"]).query).get("unp_tpcid") or [""])[0] if primary else ""
    out["kind"] = KINDS.get(tpcid) or (
        "updated" if "Here's your updated invoice" in lines else "new" if "Here's your invoice" in lines else "unknown"
    )

    if m := TITLE_NEW.match(reader.title) or TITLE_UPDATED.match(reader.title):
        out["merchant"], out["number"] = m[1].strip(), m[2].strip()
    if primary and primary["isPaypal"] and (m := INVOICE_ID.search(urlparse(primary["url"]).path)):
        out["invoiceId"] = m[1]  # an id from a link that does not lead to PayPal means nothing

    hello = next((ln[len("Hello, "):].strip() for ln in lines if ln.startswith("Hello, ")), None)
    if hello and EMAIL.match(hello):
        out["recipientEmail"] = hello.lower()
    elif hello:
        out["recipientName"] = hello

    head = next((HEAD_MONEY.match(ln) for ln in lines if HEAD_MONEY.match(ln)), None)
    if head:
        out["amount"], out["currency"] = Decimal(head[1].replace(",", "")), head[2]
    out["dueDate"] = next((d for ln in lines if (d := _month_day_year(ln))), None)

    if "Note from seller" in lines:
        start = lines.index("Note from seller") + 1
        end = next((i for i in range(start, len(lines)) if lines[i] in ("Invoice summary", "Subtotal", "Total")), len(lines))
        out["note"] = "\n".join(lines[start:end]) or None

    number_line = next((i for i, ln in enumerate(lines) if ln.startswith("Invoice number:")), None)
    if number_line is not None:
        out["number"] = out["number"] or lines[number_line].split(":", 1)[1].strip() or None
        stop = next((i for i in range(number_line + 1, len(lines)) if lines[i] in ("Subtotal", "Total")), len(lines))
        items: list[dict] = []
        for ln in lines[number_line + 1:stop]:
            if m := LINE_ITEM.match(ln):
                if items:
                    items[-1].update(quantity=m[1], unitAmount=m[2].replace(",", ""))
            elif PLAIN_MONEY.match(ln):
                continue  # the line total, derived from quantity and unit amount
            else:
                items.append({"name": ln, "description": None, "quantity": None, "unitAmount": None})
        out["items"] = items or None
    return out

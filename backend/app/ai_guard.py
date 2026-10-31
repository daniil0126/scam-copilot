"""Guards around the LLM: what goes in (minimal personal data) and what comes out (grounded, cautious).

Pure functions, no network, no database. Used by `llm.py`.

Input side: `mask_text`, `mask_email`, `mask_phone`, `strip_url_query` remove personal data the explanation does not need.
Output side: `ungrounded_values` finds emails, links, phone numbers and amounts that the model named but that were not in
its input (an invented value is dropped, never repaired), and `overclaims` finds sentences that state fraud or safety as a
fact. Both are conservative on purpose: a dropped explanation costs little, an invented one costs trust.
"""
import re
from decimal import Decimal, InvalidOperation

# --- input side -------------------------------------------------------------------------------------------------

_EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
# A country code, an optional area code in brackets, then digits with spaces, dots or hyphens. Brackets inside the number
# are not allowed, so "349.99 (349.99 USD)" is two amounts and not one long phone number.
_PHONE = re.compile(r"(?<![\w.])\+?(?:\d{1,3}[\s.\-]?)?(?:\(\d{1,4}\)[\s.\-]?)?\d[\d\s.\-]{5,}\d(?![\w])")
_DATE = re.compile(r"^\d{1,4}[.\-]\d{1,2}[.\-]\d{1,4}$")  # 2026-10-31, 31.10.2026
_URL = re.compile(r"(?:https?://|www\.)[^\s<>\"']+", re.IGNORECASE)

MASKED_PHONE = "[phone]"


def mask_email(email: str) -> str:
    """`billing@acme.example.com` -> `b***@acme.example.com`. The domain stays: a lookalike domain is the evidence."""
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}" if domain else email


def _is_phone(candidate: str) -> bool:
    digits = sum(c.isdigit() for c in candidate)
    return 8 <= digits <= 15 and not _DATE.match(candidate.strip())


def mask_phone(text: str) -> str:
    """Replaces phone-like numbers. A date such as 2026-10-31 is not a phone number and stays."""
    return _PHONE.sub(lambda m: MASKED_PHONE if _is_phone(m.group()) else m.group(), text)


def strip_url_query(url: str) -> str:
    """Query strings and fragments often carry tokens and ids; the host and path are what a reader needs."""
    return re.split(r"[?#]", url, maxsplit=1)[0]


def mask_text(text: str | None) -> str:
    """Emails keep their domain, phone numbers are replaced, links lose their query string."""
    if not text:
        return ""
    text = _URL.sub(lambda m: strip_url_query(m.group()), text)
    text = _EMAIL.sub(lambda m: mask_email(m.group()), text)
    return mask_phone(text)


# --- output side ------------------------------------------------------------------------------------------------

# Emails also match their masked form (`b***@acme.example.com`): echoing it is fine, inventing another domain is not.
_OUT_EMAIL = re.compile(r"[\w.+\-*]+@[\w\-]+(?:\.[\w\-]+)+")
_OUT_URL = re.compile(r"(?:https?://|www\.)[^\s<>\"')\]]+", re.IGNORECASE)
_NUMBER = r"\d[\d,]*(?:\.\d+)?"
_AMOUNTS = (
    re.compile(rf"[$€£¥]\s?{_NUMBER}"),                       # $349.99
    re.compile(rf"\b{_NUMBER}\s?\b[A-Z]{{3}}\b"),            # 349.99 USD
    re.compile(rf"\b[A-Z]{{3}}\s?{_NUMBER}"),                # USD 349.99
    re.compile(r"\b\d{1,3}(?:,\d{3})*\.\d{2}\b|\b\d+\.\d{2}\b"),  # bare 349.99
)
_ANY_NUMBER = re.compile(_NUMBER)


def _number(token: str) -> Decimal | None:
    match = _ANY_NUMBER.search(token)
    if not match:
        return None
    try:
        return Decimal(match.group().replace(",", "")).normalize()
    except InvalidOperation:
        return None


def _source_numbers(source: str) -> set[Decimal]:
    return {n for m in _ANY_NUMBER.finditer(source) if (n := _number(m.group())) is not None}


def ungrounded_values(text: str, source: str) -> list[str]:
    """Values in `text` (emails, links, phone numbers, amounts) that do not occur in `source`.

    `source` is everything the model was given. An amount is compared as a number ("100" equals "100.00").
    """
    if not text:
        return []
    low_source = source.lower()
    missing: list[str] = []

    for m in _OUT_EMAIL.finditer(text):
        if m.group().lower() not in low_source:
            missing.append(m.group())
    for m in _OUT_URL.finditer(text):
        url = m.group().rstrip(".,;:!?")
        if strip_url_query(url).lower() not in low_source:
            missing.append(url)
    for m in _PHONE.finditer(text):
        if _is_phone(m.group()) and re.sub(r"\D", "", m.group()) not in re.sub(r"\D", "", source):
            missing.append(m.group().strip())

    numbers = _source_numbers(source)
    seen_spans: list[tuple[int, int]] = []
    for pattern in _AMOUNTS:
        for m in pattern.finditer(text):
            if any(s <= m.start() < e or s < m.end() <= e for s, e in seen_spans):
                continue  # already judged as part of a longer match
            seen_spans.append(m.span())
            value = _number(m.group())
            if value is not None and value not in numbers:
                missing.append(m.group().strip())
    return list(dict.fromkeys(missing))


_FRAUD_NOUN = r"(?:scam(?:mer)?s?|fraud(?:ulent)?|phishing|fake|forged|counterfeit)"
_SURE = r"(?:definitely|certainly|clearly|obviously|undoubtedly|absolutely|surely)"
_OVERCLAIMS = [
    re.compile(rf"\b(?:is|are|was|were)\s+(?:{_SURE}\s+)?(?:an?\s+)?{_FRAUD_NOUN}\b", re.I),
    re.compile(rf"\bit'?s\s+(?:{_SURE}\s+)?(?:an?\s+)?{_FRAUD_NOUN}\b", re.I),
    re.compile(rf"\b{_SURE}\s+(?:an?\s+)?{_FRAUD_NOUN}\b", re.I),
    re.compile(r"\b(?:confirmed|proven|verified)\s+(?:fraud|scam)\b", re.I),
    re.compile(r"\b(?:is|are)\s+(?:completely\s+|totally\s+|definitely\s+|certainly\s+)?(?:safe|legit|legitimate|genuine|trustworthy)\b", re.I),
    re.compile(r"\bsafe to pay\b|\bno risk\b|\bnothing to worry\b", re.I),
    re.compile(r"\bэто\s+(?:точно\s+|явно\s+|определённо\s+|определенно\s+)?(?:мошенничество|мошенники|обман|скам|фишинг)", re.I),
    re.compile(r"\b(?:является|есть)\s+мошенничеством\b|\bточно\s+мошенн\w+|\bмошеннический\s+счёт\b", re.I),
    re.compile(r"\b(?:безопасен|безопасна|безопасно|можно\s+(?:смело\s+)?платить)\b", re.I),
]


# A clause that doubts or denies ("nothing proves that it is legitimate", "not sure it is a scam") does not state a fact.
_HEDGE = re.compile(
    r"\b(?:not|no|nothing|never|cannot|can't|couldn't|without|unless|whether|if|may|might|could|unclear|unknown|"
    r"neither|nor|does(?:n't| not)|do(?:n't| not)|нет|не|ничто|нельзя|если|ли)\b|n't", re.I)
_CLAUSE_END = re.compile(r"[.;:,!?\n]")


def _asserted(pattern: re.Pattern, text: str) -> bool:
    for m in pattern.finditer(text):
        clause = text[: m.start()]
        cut = max((c.end() for c in _CLAUSE_END.finditer(clause)), default=0)
        if not _HEDGE.search(clause[cut:]):
            return True
    return False


def overclaims(text: str) -> bool:
    """True when the text states fraud or safety as a fact. "Signs of fraud" and "needs checking" are fine."""
    return any(_asserted(p, text or "") for p in _OVERCLAIMS)


REDACTED = "[not in the invoice data]"


def redact_ungrounded(text: str, source: str) -> str:
    """Chat answers are not dropped for one invented value: the value is replaced so the rest can be read."""
    for value in ungrounded_values(text, source):
        text = text.replace(value, REDACTED)
    return text

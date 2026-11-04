from __future__ import annotations

from .config import RulesConfig
from .types import HistoricalInvoice, Invoice, VendorHistory


class Relationship:
    __slots__ = ("otherSenderKey", "sharedLinks", "sharedPhones", "sharedSignatures", "kind")

    def __init__(self, other_sender_key: str,
                 shared_links: list[str], shared_phones: list[str],
                 shared_signatures: list[str], min_independent: int):
        self.otherSenderKey = other_sender_key
        self.sharedLinks = shared_links
        self.sharedPhones = shared_phones
        self.sharedSignatures = shared_signatures
        independent = sum(bool(x) for x in (shared_links, shared_phones, shared_signatures))
        self.kind = "relationship" if independent >= min_independent else "observation"

    def as_dict(self) -> dict:
        return {
            "otherSenderKey": self.otherSenderKey,
            "kind": self.kind,
            "sharedLinks": self.sharedLinks,
            "sharedPhones": self.sharedPhones,
            "sharedSignatures": self.sharedSignatures,
        }

    def __repr__(self) -> str:
        return f"Relationship({self.kind} with {self.otherSenderKey})"


def _links(invoice_or_hist) -> set[str]:
    return {l for l in (invoice_or_hist.paymentLinks or []) if l}


def _signature(h: HistoricalInvoice) -> str | None:
    return h.itemsSignature


def find_relationships(
    invoice: Invoice, history: VendorHistory, current_signature: str | None = None,
    config: RulesConfig | None = None,
) -> list[Relationship]:
    """Связи текущего отправителя с другими отправителями через независимые признаки.

    Признаки: общие ссылки, общие телефоны (в истории не хранится — берём из knownContacts),
    общие itemsSignature. Порог независимых совпадений — config.relationship_min_independent_matches
    (по умолчанию 2): relationship, иначе observation.
    """
    cfg = config or RulesConfig()
    current_links = _links(invoice)
    current_phone = invoice.senderPhone
    current_sig = current_signature

    by_sender: dict[str, dict] = {}
    for h in history.otherSenderInvoices:
        key = _sender_key(h)
        if key is None or key == history.senderKey:
            continue
        bucket = by_sender.setdefault(key, {"links": set(), "signatures": set()})
        bucket["links"] |= _links(h)
        sig = _signature(h)
        if sig:
            bucket["signatures"].add(sig)

    for c in history.knownContacts:
        if not c.phone:
            continue
        by_sender.setdefault(c.email or c.name or "", {"links": set(), "signatures": set(), "phone": c.phone})

    out: list[Relationship] = []
    for other_key, bucket in by_sender.items():
        if not other_key:
            continue
        shared_links = sorted(current_links & bucket.get("links", set()))
        shared_sigs = sorted({current_sig} & bucket.get("signatures", set())) if current_sig else []
        shared_phones = [current_phone] if current_phone and bucket.get("phone") == current_phone else []

        if not (shared_links or shared_sigs or shared_phones):
            continue

        out.append(Relationship(
            other_sender_key=other_key,
            shared_links=shared_links,
            shared_phones=shared_phones,
            shared_signatures=shared_sigs,
            min_independent=cfg.relationship_min_independent_matches,
        ))

    out.sort(key=lambda r: (r.kind != "relationship", r.otherSenderKey))
    return out


def _sender_key(h: HistoricalInvoice) -> str | None:
    if h.senderEmail:
        return h.senderEmail.lower()
    if h.senderName:
        return h.senderName
    return None
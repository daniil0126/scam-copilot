from __future__ import annotations

import re

from .config import RulesConfig
from .rule_d import KNOWN_BRANDS, OFFICIAL_DOMAINS
from .types import Invoice, Signal, VendorHistory


RULE_VERSION_SUFFIX = "text"

PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")

SCAM_WORDS = (
    "cancel", "refund", "call us", "call now", "unauthorized", "unauthorised",
    "suspicious", "renewed", "auto-renew", "subscription", "charged",
    "dispute", "helpline", "support number",
)

def rule_text(invoice: Invoice, history: VendorHistory, config: RulesConfig) -> list[Signal]:
    rule_version = f"{RULE_VERSION_SUFFIX}-{config.version}"
    signals: list[Signal] = []

    # --- BRAND_IMPERSONATION: не зависит от note, проверяем всегда ---
    name_l = (invoice.senderName or "").lower()
    email = invoice.senderEmail or ""
    domain = email.split("@")[-1].lower() if "@" in email else ""
    for brand in KNOWN_BRANDS:
        if brand not in name_l:
            continue
        official = OFFICIAL_DOMAINS.get(brand, set())
        if any(domain == d or domain.endswith("." + d) for d in official):
            break
        signals.append(Signal(
            type="BRAND_IMPERSONATION", severity="HIGH", status="DETECTED",
            evidence=f"Имя «{invoice.senderName}» содержит бренд {brand}, домен {domain or '—'} не принадлежит бренду",
            evidenceData={"brand": brand, "senderName": invoice.senderName, "senderEmail": invoice.senderEmail},
            source="RULE_ENGINE", ruleVersion=rule_version,
        ))
        break

    # --- PHONE_IN_TEXT / SCAM_WORDING: только при непустом note ---
    note = invoice.note or ""
    if note.strip():
        if PHONE_RE.search(note):
            signals.append(Signal(
                type="PHONE_IN_TEXT", severity="HIGH", status="DETECTED",
                evidence="В тексте инвойса есть номер телефона",
                evidenceData={"noteExcerpt": note[:200]},
                source="RULE_ENGINE", ruleVersion=rule_version,
            ))

        lowered = note.lower()
        hits = [w for w in SCAM_WORDS if w in lowered]
        if hits:
            signals.append(Signal(
                type="SCAM_WORDING", severity="MEDIUM", status="DETECTED",
                evidence=f"Типичные scam-слова: {', '.join(hits[:3])}",
                evidenceData={"hits": hits[:5]},
                source="RULE_ENGINE", ruleVersion=rule_version,
            ))

    return signals
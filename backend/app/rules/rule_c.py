from __future__ import annotations

from .config import RulesConfig
from .types import Invoice, Signal, VendorHistory


RULE_VERSION_SUFFIX = "vendor"


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _domain(email: str | None) -> str | None:
    return email.split("@", 1)[1].lower() if email and "@" in email else None


def rule_c(invoice: Invoice, history: VendorHistory, config: RulesConfig) -> list[Signal]:
    rule_version = f"{RULE_VERSION_SUFFIX}-{config.version}"

    # Нет истории вообще — это факт «новый поставщик», а не «мало данных для сравнения».
    if not history.priorInvoices and not history.knownContacts:
        return [Signal(
            type="NEW_SENDER", severity="MEDIUM", status="DETECTED",
            evidence="Поставщик ранее не встречался в истории",
            evidenceData={"priorInvoices": 0, "knownContacts": 0},
            source="RULE_ENGINE", ruleVersion=rule_version,
        )]

    known_emails = {c.email.lower() for c in history.knownContacts if c.email}
    known_names = {c.name for c in history.knownContacts if c.name}
    known_domains = {d for d in (_domain(e) for e in known_emails) if d}

    current_email = (invoice.senderEmail or "").lower() or None
    current_domain = _domain(current_email)
    current_name = invoice.senderName

    signals: list[Signal] = []
    email_mismatch = False

    # 1. email сменился → SENDER_MISMATCH (бывший payee, HIGH)
    if current_email and known_emails and current_email not in known_emails:
        email_mismatch = True
        signals.append(Signal(
            type="SENDER_MISMATCH", severity="HIGH", status="DETECTED",
            evidence=f"Платёжный email {current_email} отличается от известных",
            evidenceData={"currentEmail": current_email, "knownEmails": sorted(known_emails)[:5]},
            source="RULE_ENGINE", ruleVersion=rule_version,
        ))
    # 2. email тот же, но имя сменилось → SENDER_NAME_CHANGED
    elif current_email in known_emails and current_name and known_names and current_name not in known_names:
        signals.append(Signal(
            type="SENDER_NAME_CHANGED", severity="MEDIUM", status="DETECTED",
            evidence=f"Тот же PayPal-аккаунт, новое имя: «{current_name}»",
            evidenceData={"currentName": current_name, "knownNames": sorted(known_names)[:5]},
            source="RULE_ENGINE", ruleVersion=rule_version,
        ))

    # 3. похожий домен (расстояние Левенштейна) — только если email-mismatch ещё не сработал,
    #    чтобы не дублировать SENDER_MISMATCH в том же family и не шуметь в evidence.
    if not email_mismatch and current_domain and known_domains and current_domain not in known_domains:
        for known_d in known_domains:
            dist = _levenshtein(current_domain, known_d)
            if dist <= config.vendor_domain_distance_max:
                signals.append(Signal(
                    type="SENDER_MISMATCH", severity="HIGH", status="DETECTED",
                    evidence=f"Домен {current_domain} похож на известный {known_d}, но не совпадает",
                    evidenceData={"currentDomain": current_domain, "knownDomain": known_d, "distance": dist},
                    source="RULE_ENGINE", ruleVersion=rule_version,
                ))
                break

    return signals
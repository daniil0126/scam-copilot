from __future__ import annotations

from datetime import datetime

from .types import ContactSnapshot, HistoricalInvoice, VendorHistory


class ContactChange:
    __slots__ = ("field", "old", "new", "firstSeen", "lastSeen")

    def __init__(self, field: str, old: str | None, new: str | None,
                 first_seen: datetime | None, last_seen: datetime | None):
        self.field = field
        self.old = old
        self.new = new
        self.firstSeen = first_seen
        self.lastSeen = last_seen

    def as_dict(self) -> dict:
        return {
            "field": self.field, "old": self.old, "new": self.new,
            "firstSeen": self.firstSeen.isoformat() if self.firstSeen else None,
            "lastSeen": self.lastSeen.isoformat() if self.lastSeen else None,
        }

    def __repr__(self) -> str:
        return f"ContactChange({self.field}: {self.old!r} -> {self.new!r})"


def extract_contact_changes(history: VendorHistory) -> list[ContactChange]:
    """История изменений email/имени/телефона по известным контактам и прошлым инвойсам.

    Упорядочивает knownContacts + priorInvoices по firstSeen (или createdAt) и фиксирует переходы.
    """
    timeline: list[dict] = []

    for c in history.knownContacts:
        timeline.append({
            "email": c.email, "name": c.name, "phone": c.phone,
            "when": c.firstSeen or c.lastSeen,
        })

    for h in history.priorInvoices:
        timeline.append({
            "email": h.senderEmail, "name": h.senderName, "phone": None,
            "when": h.createdAt,
        })

    timeline = [e for e in timeline if e["when"] is not None]
    timeline.sort(key=lambda e: e["when"])

    changes: list[ContactChange] = []
    for field in ("email", "name", "phone"):
        prev_value: str | None = None
        prev_when: datetime | None = None
        for entry in timeline:
            value = entry.get(field)
            if value is None:
                continue
            if prev_value is None:
                prev_value = value
                prev_when = entry["when"]
                continue
            if value != prev_value:
                changes.append(ContactChange(
                    field=field, old=prev_value, new=value,
                    first_seen=prev_when, last_seen=entry["when"],
                ))
                prev_value = value
                prev_when = entry["when"]

    return changes
"""Where an alert goes. The core decides that an alert exists; a channel only delivers it.

To add email or browser notifications, write a class with `name` and `deliver()` and add it to `CHANNELS` (or pass it to
`service.process_result`). Nothing in the core changes.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.notifications.models import Notification


@dataclass(frozen=True)
class AlertDraft:
    account_id: str
    invoice_id: str
    content_hash: str  # the invoice version the alert is about
    event_type: str
    risk_level: str
    title: str
    message: str
    signals: list[str]
    detected_at: datetime

    @property
    def dedup_key(self) -> tuple[str, str, str, str]:
        return (self.account_id, self.invoice_id, self.content_hash, self.event_type)


class NotificationChannel(Protocol):
    name: str

    def deliver(self, db: Session, draft: AlertDraft) -> bool:
        """Delivers the alert once. Must be idempotent for a `draft.dedup_key`: a second call delivers nothing and
        returns False. Returns True when this call delivered it. The caller owns the commit."""


class InAppChannel:
    """The alert is a row the extension reads through `GET /notifications`."""

    name = "in_app"

    def deliver(self, db: Session, draft: AlertDraft) -> bool:
        account, invoice, version, event = draft.dedup_key
        seen = db.scalar(select(Notification.row_id).where(
            Notification.account_id == account, Notification.invoice_id == invoice,
            Notification.content_hash == version, Notification.event_type == event,
        ))
        if seen is not None:
            return False
        db.add(Notification(
            account_id=account, invoice_id=invoice, content_hash=version, event_type=event, risk_level=draft.risk_level,
            title=draft.title, message=draft.message, signals=draft.signals, detected_at=draft.detected_at,
        ))
        return True


CHANNELS: list[NotificationChannel] = [InAppChannel()]

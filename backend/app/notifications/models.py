"""Tables of the alerts. Defined here, next to the code that uses them, on the shared `Base`; the schema owner can move
them into models.py in his own PR (docs/plans/team/WORKFLOW.md, section 1)."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Notification(Base):
    __tablename__ = "notifications"
    # The dedup key (contracts.md, section 3): an invoice version raises one alert per event type, however often it is processed.
    __table_args__ = (UniqueConstraint("account_id", "invoice_id", "content_hash", "event_type", name="uq_notification_event"),)

    row_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String, index=True)
    invoice_id: Mapped[str] = mapped_column(String, index=True)
    content_hash: Mapped[str] = mapped_column(String)
    event_type: Mapped[str] = mapped_column(String)
    risk_level: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(String)
    signals: Mapped[list] = mapped_column(JSON)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AlertSettings(Base):
    __tablename__ = "alert_settings"

    account_id: Mapped[str] = mapped_column(String, primary_key=True)
    alert_threshold: Mapped[str] = mapped_column(String, default="HIGH")
    categories: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Check(Base):
    __tablename__ = "checks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    # One entry per PayPal invoice (run_check updates it). Unique, so a race fails loudly instead of leaving a duplicate.
    paypal_invoice_id: Mapped[str] = mapped_column(String, unique=True)
    supplier_name: Mapped[str] = mapped_column(String, index=True)
    supplier_email: Mapped[str] = mapped_column(String, default="", index=True)
    number: Mapped[str] = mapped_column(String)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String)
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    result: Mapped[dict] = mapped_column(JSON)


class MonitoredInvoice(Base):
    """An invoice of a connected account that the monitor has seen. `current_version_hash` points into `invoice_versions`."""

    __tablename__ = "invoices"

    account_id: Mapped[str] = mapped_column(String, primary_key=True)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    current_version_hash: Mapped[str] = mapped_column(String)
    # Hash of the last list item seen. A list item that hashes the same needs no detail request.
    list_hash: Mapped[str] = mapped_column(String, default="")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class InvoiceVersion(Base):
    __tablename__ = "invoice_versions"
    __table_args__ = (UniqueConstraint("account_id", "invoice_id", "content_hash"),)

    row_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String, index=True)
    invoice_id: Mapped[str] = mapped_column(String, index=True)
    content_hash: Mapped[str] = mapped_column(String)
    normalized: Mapped[dict] = mapped_column(JSON)
    raw: Mapped[dict] = mapped_column(JSON)
    seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SyncState(Base):
    __tablename__ = "sync_state"

    account_id: Mapped[str] = mapped_column(String, primary_key=True)
    last_successful_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    state: Mapped[str] = mapped_column(String, default="ACTIVE")  # ACTIVE / PAUSED / ERROR
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)


class InvoiceEmail(Base):
    """One PayPal notification email about an invoice. Only extracted fields are kept, never the HTML.

    An email is an event ("issued", "updated"), not a content version: two update emails that look the same
    (the note changed, which the email does not show) are two events, so `message_key` is built from the email
    itself and not from the invoice content alone.
    """

    __tablename__ = "invoice_emails"

    row_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_key: Mapped[str] = mapped_column(String, unique=True)
    invoice_id: Mapped[str] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String)  # new / updated / unknown
    template: Mapped[str | None] = mapped_column(String, nullable=True)
    normalized: Mapped[dict] = mapped_column(JSON)
    links: Mapped[list] = mapped_column(JSON)  # host and flags per link, query strings removed
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

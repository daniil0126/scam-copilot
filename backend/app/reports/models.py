"""Tables of the reports (contracts.md, section 3: `analyses`, `audit_reports`). Defined next to the code that uses them,
on the shared `Base`; the schema owner can move them into models.py in his own PR (docs/plans/team/WORKFLOW.md, section 1).

`Analysis` rows are never overwritten: an invoice version analysed by one engine version is stored once. Its level,
score, supplier, month and week are copied into columns so that every figure of a report is an SQL aggregate.
"""
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Analysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (
        UniqueConstraint("account_id", "invoice_id", "content_hash", "engine_version", name="uq_analysis_version"),
        Index("ix_analyses_account_month", "account_id", "month"),
    )

    row_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String)
    invoice_id: Mapped[str] = mapped_column(String, index=True)
    content_hash: Mapped[str] = mapped_column(String)
    engine_version: Mapped[str] = mapped_column(String)
    month: Mapped[str] = mapped_column(String)          # "2026-10", of analyzed_at (UTC)
    week_start: Mapped[date] = mapped_column(Date)      # the Monday of that week
    risk_level: Mapped[str] = mapped_column(String)     # LOW / MEDIUM / HIGH / CRITICAL
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    supplier_name: Mapped[str] = mapped_column(String, default="")
    supplier_email: Mapped[str] = mapped_column(String, default="")
    result: Mapped[dict] = mapped_column(JSON)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AnalysisSignal(Base):
    """A sign of one analysis that falls in a report category, so that categories are counted in SQL."""

    __tablename__ = "analysis_signals"

    row_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.row_id"), index=True)
    category: Mapped[str] = mapped_column(String)       # VENDOR_IMPERSONATION / POTENTIAL_DUPLICATE / SUSPICIOUS_PAYMENT_LINK
    signal_type: Mapped[str] = mapped_column(String)


class AuditReport(Base):
    __tablename__ = "audit_reports"
    __table_args__ = (UniqueConstraint("account_id", "month", "version", name="uq_report_version"),)

    row_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String, index=True)
    month: Mapped[str] = mapped_column(String)
    version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    data: Mapped[dict] = mapped_column(JSON)

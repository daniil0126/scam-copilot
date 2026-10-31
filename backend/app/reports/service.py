"""Writes analyses and builds the monthly report and the monitoring summary. Callers own the commit.

Every figure is an SQL aggregate over `analyses` of one account. A month without analyses is an empty report, not zeros.
"""
import re
from datetime import date, datetime, timedelta

from sqlalchemy import case, distinct, func, select
from sqlalchemy.orm import Session

from app.notifications import categories
from app.reports.models import Analysis, AnalysisSignal, AuditReport

ENGINE_VERSION = "legacy-1"
MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
FLAGGED = ("HIGH", "CRITICAL")
REPORT_CATEGORIES = ("POTENTIAL_DUPLICATE", "VENDOR_IMPERSONATION", "SUSPICIOUS_PAYMENT_LINK")
WORDING = ("The report counts suspicious signs detected by the rules. They need checking with the supplier "
           "and are not confirmed fraud.")


def month_of(moment: datetime) -> str:
    return moment.strftime("%Y-%m")


def week_start(moment: datetime) -> date:
    day = moment.date()
    return day - timedelta(days=day.weekday())


def record_analysis(
    db: Session, account: str, invoice_id: str, content_hash: str, result: dict,
    *, engine: str = ENGINE_VERSION, now: datetime | None = None,
) -> bool:
    """Stores the analysis of one invoice version once. True when this call stored it."""
    exists = db.scalar(select(Analysis.row_id).where(
        Analysis.account_id == account, Analysis.invoice_id == invoice_id,
        Analysis.content_hash == content_hash, Analysis.engine_version == engine))
    if exists is not None:
        return False
    now = now or datetime.utcnow()
    supplier = (result.get("invoice") or {}).get("supplier") or {}
    row = Analysis(
        account_id=account, invoice_id=invoice_id, content_hash=content_hash, engine_version=engine,
        month=month_of(now), week_start=week_start(now), risk_level=categories.risk_level(result),
        risk_score=categories.risk_score(result), supplier_name=supplier.get("name") or "",
        supplier_email=supplier.get("email") or "", result=result, analyzed_at=now)
    db.add(row)
    db.flush()  # the id of the row for its signals
    for category, types in categories.category_hits(result).items():
        for signal_type in types:
            db.add(AnalysisSignal(analysis_id=row.row_id, category=category, signal_type=signal_type))
    return True


def _category_counts(db: Session, where: list) -> dict[str, int]:
    """Invoices with at least one sign of each category, among the analyses selected by `where`."""
    rows = db.execute(
        select(AnalysisSignal.category, func.count(distinct(Analysis.invoice_id)))
        .join(Analysis, Analysis.row_id == AnalysisSignal.analysis_id).where(*where)
        .group_by(AnalysisSignal.category)).all()
    found = dict(rows)
    return {name: found.get(name, 0) for name in REPORT_CATEGORIES}


def build_monthly(db: Session, account: str, month: str) -> dict:
    if not MONTH_RE.match(month):
        raise ValueError("month must look like 2026-10")
    where = [Analysis.account_id == account, Analysis.month == month]
    analyses, invoices = db.execute(select(func.count(), func.count(distinct(Analysis.invoice_id))).where(*where)).one()
    if not analyses:
        return {"month": month, "empty": True, "message": "No invoices were analysed in this month.", "wording": WORDING}

    levels = dict(db.execute(select(Analysis.risk_level, func.count()).where(*where).group_by(Analysis.risk_level)).all())
    cats = _category_counts(db, where)
    vendors = db.execute(
        select(Analysis.supplier_email, func.max(Analysis.supplier_name), func.count(distinct(Analysis.invoice_id)))
        .where(*where, Analysis.risk_level.in_(FLAGGED), Analysis.supplier_email != "")
        .group_by(Analysis.supplier_email)
        .order_by(func.count(distinct(Analysis.invoice_id)).desc(), Analysis.supplier_email).limit(5)).all()
    weeks = db.execute(
        select(Analysis.week_start, func.count(), func.avg(Analysis.risk_score),
               func.sum(case((Analysis.risk_level.in_(FLAGGED), 1), else_=0)))
        .where(*where).group_by(Analysis.week_start).order_by(Analysis.week_start)).all()
    review, seen = [], set()
    for row in db.scalars(select(Analysis).where(*where, Analysis.risk_level.in_(FLAGGED))
                          .order_by(Analysis.risk_score.desc(), Analysis.row_id).limit(100)):
        if row.invoice_id not in seen and len(review) < 20:
            seen.add(row.invoice_id)
            review.append({"invoiceId": row.invoice_id, "riskLevel": row.risk_level, "riskScore": row.risk_score,
                           "supplierName": row.supplier_name or None,
                           "signs": [s["label"] for s in categories.detected(row.result)
                                     if categories.SEVERITY_RANK[s["severity"]] >= categories.SEVERITY_RANK["MEDIUM"]][:5]})
    return {
        "month": month, "empty": False, "wording": WORDING, "analyses": analyses, "invoices": invoices,
        "byLevel": {level: levels.get(level, 0) for level in categories.RISK_LEVELS},
        "potentialDuplicates": cats["POTENTIAL_DUPLICATE"], "vendorAnomalies": cats["VENDOR_IMPERSONATION"],
        "suspiciousLinks": cats["SUSPICIOUS_PAYMENT_LINK"],
        "topFlaggedSuppliers": [{"supplierEmail": e, "supplierName": n or None, "flaggedInvoices": c} for e, n, c in vendors],
        "weeklyTrend": [{"weekStart": w.isoformat(), "analyses": c, "averageScore": round(float(avg), 1),
                         "highOrCritical": int(flagged)} for w, c, avg, flagged in weeks],
        "manualReview": review,
    }


def latest_report(db: Session, account: str, month: str) -> dict | None:
    row = db.scalars(select(AuditReport).where(AuditReport.account_id == account, AuditReport.month == month)
                     .order_by(AuditReport.version.desc()).limit(1)).first()
    return _with_meta(row) if row else None


def _with_meta(row: AuditReport) -> dict:
    return {**row.data, "version": row.version, "createdAt": row.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"), "saved": True}


def save_monthly(db: Session, account: str, month: str, *, now: datetime | None = None) -> dict:
    """Builds the report and stores it as the next version of that month."""
    data = build_monthly(db, account, month)
    version = (db.scalar(select(func.max(AuditReport.version)).where(
        AuditReport.account_id == account, AuditReport.month == month)) or 0) + 1
    row = AuditReport(account_id=account, month=month, version=version, created_at=now or datetime.utcnow(), data=data)
    db.add(row)
    db.flush()
    return _with_meta(row)


def monitoring_summary(db: Session, account: str) -> dict:
    """Counters for the dashboard: the latest analysis of each invoice, and the last detections."""
    latest = select(func.max(Analysis.row_id)).where(Analysis.account_id == account).group_by(Analysis.invoice_id)
    where = [Analysis.row_id.in_(latest)]
    levels = dict(db.execute(select(Analysis.risk_level, func.count()).where(*where).group_by(Analysis.risk_level)).all())
    events = db.scalars(select(Analysis).where(
        Analysis.account_id == account, Analysis.risk_level.in_(("MEDIUM", *FLAGGED)))
        .order_by(Analysis.row_id.desc()).limit(10)).all()
    return {
        "invoices": sum(levels.values()), "high": levels.get("HIGH", 0), "critical": levels.get("CRITICAL", 0),
        "potentialDuplicates": _category_counts(db, where)["POTENTIAL_DUPLICATE"],
        "vendorAnomalies": _category_counts(db, where)["VENDOR_IMPERSONATION"],
        "recentDetections": [{"invoiceId": e.invoice_id, "riskLevel": e.risk_level,
                              "detectedAt": e.analyzed_at.strftime("%Y-%m-%dT%H:%M:%SZ")} for e in events],
    }

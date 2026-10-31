"""Monthly report and dashboard counters (plan 12): a known set of analyses, figures checked by hand.

Needs SQLAlchemy (in-memory SQLite); skipped without it.
"""
from datetime import datetime

import pytest

sa = pytest.importorskip("sqlalchemy")
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db import Base  # noqa: E402
from app.reports import models, service  # noqa: E402,F401


def result(level, score, supplier, *findings):
    return {"level": level, "score": score, "invoice": {"supplier": {"name": supplier[0], "email": supplier[1]}},
            "findings": [{"id": i, "label": label, "severity": sev, "detail": label} for i, label, sev in findings]}


A, B, C = ("Supplier A", "a@a.test"), ("Supplier B", "b@b.test"), ("Supplier C", "c@c.test")
PHONE = ("phone", "Phone number in invoice text", "high")
PAYEE = ("payee", "Payment email changed", "high")
LINK = ("email-link", "Link leads away from PayPal", "high")


@pytest.fixture
def db():
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        # October 2026: weeks start on Mondays 5th, 12th and 19th
        service.record_analysis(session, "acc", "INV1", "h1", result("high", 70, A, PHONE), now=datetime(2026, 10, 5, 9))
        service.record_analysis(session, "acc", "INV2", "h2", result("high", 90, A, PAYEE), now=datetime(2026, 10, 14, 9))
        service.record_analysis(session, "acc", "INV3", "h3", result("low", 10, B), now=datetime(2026, 10, 14, 10))
        service.record_analysis(session, "acc", "INV4", "h4", result("medium", 45, C, LINK), now=datetime(2026, 10, 21, 9))
        service.record_analysis(session, "acc", "INV5", "h5", result("high", 75, A, PHONE), now=datetime(2026, 11, 2, 9))  # other month
        service.record_analysis(session, "other", "INV9", "h9", result("high", 95, A, PAYEE), now=datetime(2026, 10, 14, 9))  # other account
        session.commit()
        yield session


def test_the_figures_of_a_month_match_the_hand_count(db):
    report = service.build_monthly(db, "acc", "2026-10")
    assert report["empty"] is False and report["analyses"] == 4 and report["invoices"] == 4
    assert report["byLevel"] == {"LOW": 1, "MEDIUM": 1, "HIGH": 1, "CRITICAL": 1}  # INV2 is 90: critical
    assert report["vendorAnomalies"] == 1 and report["suspiciousLinks"] == 1 and report["potentialDuplicates"] == 0
    assert report["topFlaggedSuppliers"] == [{"supplierEmail": "a@a.test", "supplierName": "Supplier A", "flaggedInvoices": 2}]
    assert report["weeklyTrend"] == [
        {"weekStart": "2026-10-05", "analyses": 1, "averageScore": 70.0, "highOrCritical": 1},
        {"weekStart": "2026-10-12", "analyses": 2, "averageScore": 50.0, "highOrCritical": 1},
        {"weekStart": "2026-10-19", "analyses": 1, "averageScore": 45.0, "highOrCritical": 0},
    ]
    assert [r["invoiceId"] for r in report["manualReview"]] == ["INV2", "INV1"]


def test_a_month_without_analyses_is_an_empty_report_not_zeros(db):
    report = service.build_monthly(db, "acc", "2026-09")
    assert report["empty"] is True and "byLevel" not in report and "analyses" not in report


def test_a_report_never_contains_another_accounts_data(db):
    report = service.build_monthly(db, "other", "2026-10")
    assert report["analyses"] == 1 and report["byLevel"]["CRITICAL"] == 1 and report["vendorAnomalies"] == 1
    assert service.build_monthly(db, "nobody", "2026-10")["empty"] is True


def test_the_report_speaks_of_signs_not_of_fraud(db):
    text = service.build_monthly(db, "acc", "2026-10")["wording"].lower()
    assert "signs" in text and "not confirmed fraud" in text


def test_saving_makes_a_new_version_each_time_and_the_latest_is_returned(db):
    first = service.save_monthly(db, "acc", "2026-10", now=datetime(2026, 11, 1, 8))
    second = service.save_monthly(db, "acc", "2026-10", now=datetime(2026, 11, 1, 9))
    db.commit()
    assert (first["version"], second["version"]) == (1, 2)
    assert service.latest_report(db, "acc", "2026-10")["version"] == 2
    assert service.latest_report(db, "acc", "2026-11") is None and service.latest_report(db, "other", "2026-10") is None


def test_the_same_invoice_version_is_stored_once(db):
    assert service.record_analysis(db, "acc", "INV1", "h1", result("high", 70, A, PHONE)) is False
    assert db.scalar(sa.select(sa.func.count()).select_from(models.Analysis).where(models.Analysis.account_id == "acc")) == 5


def test_a_bad_month_is_refused(db):
    with pytest.raises(ValueError):
        service.build_monthly(db, "acc", "2026-13")


def test_the_dashboard_counts_the_latest_analysis_of_each_invoice(db):
    # INV1 gets a newer version that is low: it no longer counts as high
    service.record_analysis(db, "acc", "INV1", "h1b", result("low", 5, A), now=datetime(2026, 11, 3, 9))
    s = service.monitoring_summary(db, "acc")
    assert s["invoices"] == 5 and s["critical"] == 1 and s["high"] == 1  # INV2 critical, INV5 high
    assert s["vendorAnomalies"] == 1 and s["recentDetections"][0]["invoiceId"] == "INV5"

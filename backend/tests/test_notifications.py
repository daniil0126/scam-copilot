"""Alerts (plan 10): when a result raises one, that an invoice version raises it once, and that channels plug in.

The first block is pure. The second needs SQLAlchemy and uses an in-memory database.
"""
from datetime import datetime

import pytest

from app.notifications import categories

ALL_ON = {"alertThreshold": "HIGH", "categories": {}}


def legacy(level, score, *findings):
    """A result in the shape `scoring.score_invoice` returns."""
    return {"level": level, "score": score, "findings": [
        {"id": i, "label": label, "severity": sev, "detail": label} for i, label, sev in findings]}


PHONE = ("phone", "Phone number in invoice text", "high")
PAYEE = ("payee", "Payment email changed", "high")


# --- which result raises which alert (pure) -----------------------------------------------------------------------

def test_a_high_result_raises_one_high_risk_alert():
    plan = categories.plan_alert(legacy("high", 70, PHONE), ALL_ON)
    assert plan.event_type == "HIGH_RISK" and plan.risk_level == "HIGH"


def test_a_critical_result_raises_one_alert_that_lists_the_other_signs():
    plan = categories.plan_alert(legacy("high", 90, PAYEE, PHONE), ALL_ON)
    assert plan.event_type == "CRITICAL_RISK" and plan.risk_level == "CRITICAL"
    assert {"SENDER_MISMATCH", "PHONE_IN_TEXT"} <= set(plan.signals) and len(plan.events) >= 2


def test_a_low_result_raises_nothing():
    assert categories.plan_alert(legacy("low", 10), ALL_ON) is None


def test_the_critical_threshold_ignores_plain_high_risk():
    assert categories.plan_alert(legacy("high", 70, PHONE), {"alertThreshold": "CRITICAL", "categories": {}}) is None
    assert categories.plan_alert(legacy("high", 90, PHONE), {"alertThreshold": "CRITICAL", "categories": {}}) is not None


def test_a_disabled_category_raises_nothing():
    off = {"alertThreshold": "HIGH", "categories": {"HIGH_RISK": False}}
    assert categories.plan_alert(legacy("high", 70, PHONE), off) is None


def test_a_category_alert_without_high_risk():
    result = legacy("medium", 45, ("brand", "Possible Norton impersonation", "high"))
    plan = categories.plan_alert(result, ALL_ON)
    assert plan.event_type == "VENDOR_IMPERSONATION" and plan.signals == ["BRAND_IMPERSONATION"]


def test_the_message_speaks_of_signs_not_of_fraud():
    text = categories.alert_message(categories.plan_alert(legacy("high", 90, PAYEE), ALL_ON)).lower()
    assert "signs" in text and "fraud" not in text and "scam" not in text


# --- one alert per invoice version, in a database --------------------------------------------------------------------

@pytest.fixture
def db():
    sa = pytest.importorskip("sqlalchemy")
    from sqlalchemy.orm import sessionmaker

    from app.db import Base
    from app.notifications import models  # noqa: F401  registers the tables

    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session


def count(db, account="acc"):
    import sqlalchemy as sa
    from app.notifications.models import Notification

    return db.scalar(sa.select(sa.func.count()).select_from(Notification).where(Notification.account_id == account))


def raise_alert(db, result, version="v1", invoice="INV2-1", account="acc", **kw):
    from app.notifications import service

    out = service.process_result(db, account, invoice, version, result, **kw)
    db.commit()
    return out


def test_a_crossed_threshold_gives_one_notification(db):
    assert raise_alert(db, legacy("high", 90, PAYEE, PHONE)) is not None
    assert count(db) == 1


def test_processing_the_same_version_again_gives_none(db):
    raise_alert(db, legacy("high", 90, PAYEE))
    assert raise_alert(db, legacy("high", 90, PAYEE)) is None
    assert count(db) == 1


def test_a_changed_invoice_gives_a_new_notification(db):
    raise_alert(db, legacy("high", 90, PAYEE), version="v1")
    raise_alert(db, legacy("high", 90, PAYEE), version="v2")
    assert count(db) == 2


def test_a_disabled_category_gives_none(db):
    from app.notifications import service

    service.save_settings(db, "acc", "HIGH", {"HIGH_RISK": False})
    db.commit()
    assert raise_alert(db, legacy("high", 70, PHONE)) is None and count(db) == 0


def test_alerts_of_one_account_do_not_appear_in_another(db):
    raise_alert(db, legacy("high", 90, PAYEE), account="acc")
    assert count(db, "other") == 0


def test_a_new_channel_needs_no_change_in_the_core(db):
    class Recorder:
        name = "recorder"

        def __init__(self):
            self.seen = []

        def deliver(self, db, draft):
            self.seen.append(draft)
            return True

    rec = Recorder()
    raise_alert(db, legacy("high", 90, PAYEE), channels=[rec], now=datetime(2026, 11, 1))
    assert len(rec.seen) == 1 and rec.seen[0].invoice_id == "INV2-1" and count(db) == 0

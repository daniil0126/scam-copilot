"""From a check result to at most one alert per invoice version. Callers own the commit."""
from datetime import datetime

from sqlalchemy.orm import Session

from app.notifications import categories
from app.notifications.channels import CHANNELS, AlertDraft, NotificationChannel
from app.notifications.models import AlertSettings


def get_settings(db: Session, account: str) -> dict:
    row = db.get(AlertSettings, account)
    if row is None:
        return {"alertThreshold": categories.DEFAULT_SETTINGS["alertThreshold"],
                "categories": dict(categories.DEFAULT_SETTINGS["categories"])}
    return {"alertThreshold": row.alert_threshold,
            "categories": {**categories.DEFAULT_SETTINGS["categories"], **(row.categories or {})}}


def save_settings(db: Session, account: str, threshold: str, enabled: dict[str, bool]) -> tuple[dict, dict]:
    """Changes the threshold and the categories named in `enabled` (the others keep their value). Returns (before, after)."""
    before = get_settings(db, account)
    after = {"alertThreshold": threshold, "categories": {**before["categories"], **enabled}}
    row = db.get(AlertSettings, account)
    if row is None:
        row = AlertSettings(account_id=account)
        db.add(row)
    row.alert_threshold, row.categories, row.updated_at = threshold, after["categories"], datetime.utcnow()
    return before, after


def process_result(
    db: Session, account: str, invoice_id: str, content_hash: str, result: dict,
    *, channels: list[NotificationChannel] | None = None, now: datetime | None = None,
) -> AlertDraft | None:
    """Raises the alert a result deserves under the account's settings. Returns the draft that was delivered, or None.

    The same invoice version processed again (a webhook and a polling pass, a retry) delivers nothing the second time;
    a changed invoice has a new `content_hash` and so raises a new alert.
    """
    plan = categories.plan_alert(result, get_settings(db, account))
    if plan is None:
        return None
    draft = AlertDraft(
        account_id=account, invoice_id=invoice_id, content_hash=content_hash, event_type=plan.event_type,
        risk_level=plan.risk_level, title=categories.TITLES[plan.event_type], message=categories.alert_message(plan),
        signals=plan.signals, detected_at=now or datetime.utcnow(),
    )
    delivered = [channel.deliver(db, draft) for channel in (CHANNELS if channels is None else channels)]
    return draft if any(delivered) else None

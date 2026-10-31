"""API of the alerts and of their settings (contracts.md, section 5). Every route acts on `current_account()` only."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from typing import Literal

from app import audit_log
from app.db import get_db
from app.notifications import categories, service
from app.notifications.models import Notification
from app.security import current_account

router = APIRouter(tags=["notifications"])
PREFIX = "ntf_"


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")  # stored as naive UTC


def to_dict(n: Notification) -> dict:
    return {
        "id": f"{PREFIX}{n.row_id}", "invoiceId": n.invoice_id, "eventType": n.event_type, "riskLevel": n.risk_level,
        "detectedAt": _iso(n.detected_at), "signals": n.signals, "read": n.read_at is not None,
        "link": f"/invoices/{n.invoice_id}", "title": n.title, "message": n.message,
    }


def _unread(db: Session, account: str) -> int:
    return db.scalar(select(func.count()).select_from(Notification).where(
        Notification.account_id == account, Notification.read_at.is_(None))) or 0


@router.get("/notifications")
def list_notifications(
    unread_only: bool = Query(False, alias="unreadOnly"), limit: int = Query(50, ge=1, le=200), cursor: str | None = None,
    account: str = Depends(current_account), db: Session = Depends(get_db),
):
    """Newest first. `nextCursor` is passed back as `cursor` to get the next page."""
    query = select(Notification).where(Notification.account_id == account)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    if cursor is not None:
        if not cursor.startswith(PREFIX) or not cursor[len(PREFIX):].isdigit():
            raise HTTPException(422, "Invalid cursor")
        query = query.where(Notification.row_id < int(cursor[len(PREFIX):]))
    rows = db.scalars(query.order_by(Notification.row_id.desc()).limit(limit + 1)).all()
    items = [to_dict(r) for r in rows[:limit]]
    return {"items": items, "unread": _unread(db, account), "nextCursor": items[-1]["id"] if len(rows) > limit else None}


@router.get("/notifications/unread-count")
def unread_count(account: str = Depends(current_account), db: Session = Depends(get_db)):
    """What the extension polls for its badge."""
    return {"unread": _unread(db, account)}


@router.post("/notifications/{notification_id}/read")
def mark_read(notification_id: str, account: str = Depends(current_account), db: Session = Depends(get_db)):
    """Marks one alert read. Another account's alert is `404`, the same as one that does not exist."""
    row = None
    if notification_id.startswith(PREFIX) and notification_id[len(PREFIX):].isdigit():
        row = db.get(Notification, int(notification_id[len(PREFIX):]))
    if row is None or row.account_id != account:
        raise HTTPException(404, "Notification not found")
    if row.read_at is None:
        row.read_at = datetime.utcnow()
        db.commit()
    return to_dict(row)


class SettingsBody(BaseModel):
    alertThreshold: Literal["HIGH", "CRITICAL"]
    categories: dict[str, bool] = {}


@router.get("/monitoring/settings")
def get_settings(account: str = Depends(current_account), db: Session = Depends(get_db)):
    return service.get_settings(db, account)


@router.put("/monitoring/settings")
def put_settings(body: SettingsBody, account: str = Depends(current_account), db: Session = Depends(get_db)):
    """`alertThreshold`: the lowest level that raises a risk alert. `categories`: the ones named are switched on or off,
    the others keep their value."""
    unknown = sorted(set(body.categories) - set(categories.EVENT_PRIORITY))
    if unknown:
        raise HTTPException(422, f"Unknown categories: {', '.join(unknown)}")
    before, after = service.save_settings(db, account, body.alertThreshold, body.categories)
    audit_log.record(db, account, "settings.update", {"before": before, "after": after})
    db.commit()
    return after

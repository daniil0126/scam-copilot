"""Audit log of what a person (or the system) did to monitoring: connect, pause, resume, manual sync, settings change.

`record` only adds the row: the caller commits it together with the action, so a failed action leaves no entry and a
completed one always has one. Details never carry secrets (`clean_detail` drops anything that looks like one).
"""
import re
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import JSON, DateTime, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db import Base, get_db
from app.security import current_account

ACTIONS = ("account.connect", "monitoring.pause", "monitoring.resume", "monitoring.sync", "settings.update")
_SECRET_KEY = re.compile(r"token|secret|password|passwd|api[_-]?key|authorization|credential", re.IGNORECASE)
MAX_TEXT = 200
MAX_ITEMS = 20


class AuditEvent(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String, index=True)
    action: Mapped[str] = mapped_column(String, index=True)
    actor: Mapped[str] = mapped_column(String, default="user")  # user: asked through the API, system: done by the backend itself
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


def clean_detail(value):
    """Drops secret-looking keys and cuts long values, at any depth."""
    if isinstance(value, dict):
        return {k: clean_detail(v) for k, v in list(value.items())[:MAX_ITEMS] if not _SECRET_KEY.search(str(k))}
    if isinstance(value, (list, tuple)):
        return [clean_detail(v) for v in value[:MAX_ITEMS]]
    if isinstance(value, str):
        return value[:MAX_TEXT]
    return value if isinstance(value, (int, float, bool)) or value is None else str(value)[:MAX_TEXT]


def record(db: Session, account: str, action: str, detail: dict | None = None, actor: str = "user") -> AuditEvent:
    if action not in ACTIONS:
        raise ValueError(f"unknown audit action {action!r}")
    event = AuditEvent(account_id=account, action=action, actor=actor, detail=clean_detail(detail or {}))
    db.add(event)
    return event


router = APIRouter(tags=["audit"])


@router.get("/audit-log")
def list_audit_log(limit: int = Query(50, ge=1, le=200), account: str = Depends(current_account), db: Session = Depends(get_db)):
    """The latest entries of this account, newest first."""
    rows = db.scalars(
        select(AuditEvent).where(AuditEvent.account_id == account).order_by(AuditEvent.id.desc()).limit(limit)
    ).all()
    return {"items": [
        {"id": r.id, "action": r.action, "actor": r.actor, "detail": r.detail,
         "createdAt": r.created_at.strftime("%Y-%m-%dT%H:%M:%SZ")}
        for r in rows
    ]}

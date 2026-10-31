"""API of the monthly report and of the dashboard counters. Every route acts on `current_account()` only."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import audit_log
from app.db import get_db
from app.reports import service
from app.security import current_account

router = APIRouter(tags=["reports"])
MONTH = r"^\d{4}-(0[1-9]|1[0-2])$"


class MonthBody(BaseModel):
    month: str = Field(pattern=MONTH)


@router.get("/reports/monthly")
def get_monthly(month: str = Query(pattern=MONTH), account: str = Depends(current_account), db: Session = Depends(get_db)):
    """The latest saved report of the month, or the same figures computed now when none was saved (`saved` tells which)."""
    saved = service.latest_report(db, account, month)
    return saved or {**service.build_monthly(db, account, month), "saved": False}


@router.post("/reports/monthly")
def create_monthly(body: MonthBody, account: str = Depends(current_account), db: Session = Depends(get_db)):
    """Computes the report and stores it as a new version."""
    try:
        report = service.save_monthly(db, account, body.month)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    audit_log.record(db, account, "report.create", {"month": body.month, "version": report["version"]})
    db.commit()
    return report


@router.get("/monitoring/summary")
def summary(account: str = Depends(current_account), db: Session = Depends(get_db)):
    return service.monitoring_summary(db, account)

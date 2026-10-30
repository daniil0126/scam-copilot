"""Contract stubs (docs/plans/contracts.md v0.2): endpoints return synthetic fixtures so frontend and
rule-engine work can start. Disabled unless CONTRACT_STUBS=1; never enabled in production.
Each stub is replaced by the real implementation of its plan and removed from here."""
import json
import os
from pathlib import Path

from fastapi import APIRouter

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "contracts"
ENABLED = os.getenv("CONTRACT_STUBS") == "1"
router = APIRouter(tags=["contract-stubs"])


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@router.get("/audits/{audit_id}")
def get_audit(audit_id: str):
    return fixture("audit_progress.json")


@router.get("/audits/{audit_id}/invoices")
def get_audit_invoices(audit_id: str):
    return fixture("invoice_rows_partial.json")


@router.get("/invoices/{invoice_id}")
def get_invoice_card(invoice_id: str):
    return {"invoice": fixture("invoice_full.json"), "analysis": fixture("risk_result_critical.json"),
            "analysisStatus": "ANALYZED", "versions": [], "vendor": None}


@router.get("/monitoring")
def get_monitoring():
    return fixture("monitoring.json")


@router.get("/notifications")
def get_notifications():
    return {"items": [fixture("notification.json")], "unread": 1}

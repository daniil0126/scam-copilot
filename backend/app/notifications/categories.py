"""What an alert is about. Pure functions over a check result: no database, no network.

Two result shapes are understood, so the rule engine can replace the legacy scorer without touching alerts:
- the legacy one from `scoring.score_invoice`: `level` low/medium/high, `score` 0..100, `findings[{id,label,severity}]`;
- the contract one (`docs/plans/contracts.md`, `RiskResult`): `riskLevel`, `riskScore`, `signals[{type,severity,status}]`.

Thresholds here are initial values to be calibrated with the dataset (docs/plans/calibration.md).
"""
from dataclasses import dataclass

RISK_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
SEVERITY_RANK = {"OK": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}

# Contract bands (contracts.md section 2): 0-29 LOW, 30-59 MEDIUM, 60-79 HIGH, 80-100 CRITICAL.
CRITICAL_FROM = 80

# Legacy finding ids to contract signal types. "supplier" is told apart by its label (see `_legacy_type`).
LEGACY_TYPES = {
    "payee": "SENDER_MISMATCH", "amount": "UNUSUAL_AMOUNT", "amount_new": "UNUSUAL_AMOUNT",
    "phone": "PHONE_IN_TEXT", "link": "SUSPICIOUS_LINK", "wording": "SCAM_WORDING", "brand": "BRAND_IMPERSONATION",
    "due": "DUE_DATE_ISSUE", "email-link": "SUSPICIOUS_LINK", "email-link-text": "SUSPICIOUS_LINK",
    "email-link-other": "SUSPICIOUS_LINK", "email-amount": "UNUSUAL_AMOUNT",
}

# Signal categories: the signal types in each, and the least severity at which one is worth an alert.
SIGNAL_CATEGORIES: dict[str, tuple[frozenset[str], str]] = {
    "VENDOR_IMPERSONATION": (frozenset({"SENDER_MISMATCH", "SENDER_NAME_CHANGED", "BRAND_IMPERSONATION"}), "MEDIUM"),
    "POTENTIAL_DUPLICATE": (frozenset({"DUPLICATE_EXACT", "DUPLICATE_POTENTIAL", "DUPLICATE_SIMILAR"}), "MEDIUM"),
    # The legacy scorer reports any link in the note as MEDIUM; only a link that leads away from PayPal is HIGH.
    "SUSPICIOUS_PAYMENT_LINK": (frozenset({"SUSPICIOUS_LINK"}), "HIGH"),
}
# One alert per invoice version, about the first of these that applies; the others are listed in its signals.
EVENT_PRIORITY = ("CRITICAL_RISK", "HIGH_RISK", "VENDOR_IMPERSONATION", "POTENTIAL_DUPLICATE", "SUSPICIOUS_PAYMENT_LINK")
THRESHOLDS = ("HIGH", "CRITICAL")  # lowest level that raises a risk alert: HIGH alerts on HIGH and CRITICAL

DEFAULT_SETTINGS = {"alertThreshold": "HIGH", "categories": {event: True for event in EVENT_PRIORITY}}

TITLES = {
    "CRITICAL_RISK": "Critical risk signs detected",
    "HIGH_RISK": "High risk signs detected",
    "VENDOR_IMPERSONATION": "Signs of vendor impersonation detected",
    "POTENTIAL_DUPLICATE": "Possible duplicate invoice detected",
    "SUSPICIOUS_PAYMENT_LINK": "Suspicious payment link detected",
}
ALERT_NOTE = "These are signs that need checking, not a confirmed finding. Verify the invoice with the supplier before paying."


def risk_level(result: dict) -> str:
    """The four-level risk of a result. A legacy `high` with a score of 80 or more is CRITICAL."""
    if result.get("riskLevel") in RISK_LEVELS:
        return result["riskLevel"]
    level = str(result.get("level", "low")).upper()
    if level == "HIGH" and risk_score(result) >= CRITICAL_FROM:
        return "CRITICAL"
    return level if level in RISK_LEVELS else "LOW"


def risk_score(result: dict) -> int:
    value = result.get("riskScore", result.get("score", 0))
    return int(value) if isinstance(value, (int, float)) else 0


def _legacy_type(finding: dict) -> str | None:
    if finding["id"] == "supplier":
        return {"New supplier": "NEW_SENDER", "Supplier name changed": "SENDER_NAME_CHANGED"}.get(finding["label"])
    return LEGACY_TYPES.get(finding["id"])


def detected(result: dict) -> list[dict]:
    """The signs a result reports, as `{type, label, severity}`: passed and not-checked findings are left out.

    `type` is None for a legacy finding with no contract signal type (it still has a label).
    """
    if "signals" in result:
        return [
            {"type": s["type"], "label": s["type"].replace("_", " ").capitalize(), "severity": str(s["severity"]).upper()}
            for s in result["signals"] if s.get("status", "DETECTED") == "DETECTED"
        ]
    out = []
    for f in result.get("findings", []):
        severity = str(f.get("severity", "ok")).upper()
        if f.get("skipped") or severity == "OK" or str(f.get("id", "")).startswith("ai-"):
            continue
        out.append({"type": _legacy_type(f), "label": f["label"], "severity": severity})
    return out


def category_hits(result: dict) -> dict[str, list[str]]:
    """For each signal category, the signal types of this result that reach its alert severity."""
    signs = detected(result)
    return {
        name: sorted({s["type"] for s in signs if s["type"] in types and SEVERITY_RANK[s["severity"]] >= SEVERITY_RANK[least]})
        for name, (types, least) in SIGNAL_CATEGORIES.items()
    }


@dataclass(frozen=True)
class AlertPlan:
    event_type: str  # the alert's category; with the invoice version it is the dedup key
    risk_level: str
    signals: list[str]  # contract signal types, strongest first
    labels: list[str]  # the same signs in words, for the message
    events: list[str]  # every category that applied, enabled ones only


def plan_alert(result: dict, settings: dict) -> AlertPlan | None:
    """Whether a result is worth an alert under these settings, and what it is about. None means no alert.

    Exactly one alert comes out of one result: the first applicable category by priority. A critical invoice that also
    shows vendor impersonation is one CRITICAL_RISK alert that lists the impersonation signal, not two alerts.
    """
    level = risk_level(result)
    enabled = {**DEFAULT_SETTINGS["categories"], **settings.get("categories", {})}
    events: list[str] = []
    if level == "CRITICAL":
        events.append("CRITICAL_RISK")
    elif level == "HIGH" and settings.get("alertThreshold", "HIGH") == "HIGH":
        events.append("HIGH_RISK")
    events += [name for name, types in category_hits(result).items() if types]
    events = [e for e in EVENT_PRIORITY if e in events and enabled.get(e, True)]
    if not events:
        return None

    signs = sorted(
        (s for s in detected(result) if SEVERITY_RANK[s["severity"]] >= SEVERITY_RANK["MEDIUM"]),
        key=lambda s: -SEVERITY_RANK[s["severity"]],
    )[:5]
    types = list(dict.fromkeys(s["type"] for s in signs if s["type"]))
    return AlertPlan(events[0], level, types, list(dict.fromkeys(s["label"] for s in signs)), events)


def alert_message(plan: AlertPlan) -> str:
    signs = "; ".join(plan.labels) or "see the analysis"
    return f"Signs detected: {signs}. {ALERT_NOTE}"

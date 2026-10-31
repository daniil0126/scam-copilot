"""Evaluate the existing legacy scorer against the normalized Invoice dataset.

Run from backend/: python scripts/evaluate_dataset.py
Metrics are computed from the current run; no expected numbers are stored in code.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from app.scoring import score_invoice

DATASET = Path(__file__).resolve().parents[1] / "tests" / "dataset" / "invoices.json"
THRESHOLD = 30  # existing score_invoice level boundary: medium starts at 30


def adapt(record: dict) -> tuple[dict, SimpleNamespace | None]:
    invoice = record["invoice"]
    required = ("senderName", "amount", "currency")
    missing = [field for field in required if invoice.get(field) in (None, "")]
    if missing:
        raise ValueError("missing required scorer fields: " + ", ".join(missing))

    legacy = {
        "number": invoice.get("invoiceNumber") or invoice["id"],
        "supplier": {
            "name": invoice["senderName"],
            "email": invoice.get("senderEmail") or "",
            "phone": invoice.get("senderPhone") or "",
        },
        "amount": float(invoice["amount"]),
        "currency": invoice["currency"],
        "dueDate": invoice.get("dueDate"),
        "note": invoice.get("note") or "",
        "status": invoice.get("status") or "",
    }
    baseline = record.get("baseline")
    previous = None
    if baseline:
        previous = SimpleNamespace(
            supplier_name=baseline["senderName"],
            supplier_email=baseline["senderEmail"],
            amount=float(baseline["amount"]),
            currency=baseline["currency"],
        )
    return legacy, previous


def main() -> None:
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    tp = fp = tn = fn = skipped = 0
    details = []

    for record in payload["records"]:
        expected = record["expectedClassification"] == "suspicious"
        try:
            invoice, previous = adapt(record)
            result = score_invoice(invoice, previous, None)
        except (KeyError, TypeError, ValueError) as exc:
            skipped += 1
            details.append((record["id"], "SKIPPED", str(exc)))
            continue

        predicted = result["score"] >= THRESHOLD
        if predicted and expected:
            tp += 1
        elif predicted and not expected:
            fp += 1
        elif not predicted and not expected:
            tn += 1
        else:
            fn += 1
        details.append((record["id"], "SUSPICIOUS" if predicted else "NORMAL", f"score={result['score']}"))

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    fpr = fp / (fp + tn) if fp + tn else 0.0

    print(f"Dataset: {DATASET}")
    print(f"Records: {len(payload['records'])}; evaluated: {tp + fp + tn + fn}; skipped: {skipped}")
    print(f"Threshold: score >= {THRESHOLD}")
    print(f"TP={tp} FP={fp} TN={tn} FN={fn}")
    print(f"Precision: {precision:.3f}")
    print(f"Recall:    {recall:.3f}")
    print(f"FPR:       {fpr:.3f}")
    print("\nPer-record results:")
    for row in details:
        print(" | ".join(row))


if __name__ == "__main__":
    main()

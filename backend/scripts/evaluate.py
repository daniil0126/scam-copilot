"""Считает Precision, Recall и False Positive Rate на тестовом наборе backend/tests/dataset/cases.json.

Ничего не хардкодится: каждый случай прогоняется через оценщика, цифры считаются из его ответов.

    cd backend
    python scripts/evaluate.py                          # текущий scoring.score_invoice (legacy)
    python scripts/evaluate.py --evaluator app.rules:evaluate   # evaluate(invoice, history) -> RiskResult
    python scripts/evaluate.py --threshold HIGH --json /tmp/eval.json

Оценщик `module:function` получает (Invoice, list[Invoice]) и возвращает объект или dict с `riskLevel`
(LOW/MEDIUM/HIGH/CRITICAL) либо `level` (low/medium/high). Исключение оценщика считается пропуском
случая (он попадает в отчёт `errors`, метрики его не учитывают), а не тихим «не помечен».
"""
import argparse
import importlib
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.checks import legacy_invoice  # noqa: E402
from app.models import Check  # noqa: E402
from app.normalize import Invoice  # noqa: E402
from app.scoring import score_invoice  # noqa: E402

DATASET = ROOT / "tests" / "dataset" / "cases.json"
LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def to_check(inv: Invoice) -> Check:
    """Прошлый счёт поставщика в виде строки истории, как её читает score_invoice."""
    return Check(
        id=inv.id, paypal_invoice_id=inv.id, supplier_name=inv.senderName or "", supplier_email=inv.senderEmail or "",
        number=inv.invoiceNumber or "", amount=float(inv.amount) if inv.amount is not None else 0.0,
        currency=inv.currency or "", checked_at=datetime.fromisoformat(f"{inv.invoiceDate}T00:00:00"), result={},
    )


def legacy_evaluator(invoice: Invoice, history: list[Invoice]) -> str:
    """Тот же выбор истории, что в checks.run_check: последний счёт с тем же именем и с тем же email."""
    rows = sorted((to_check(h) for h in history), key=lambda c: c.checked_at, reverse=True)
    previous = next((c for c in rows if c.supplier_name == (invoice.senderName or "")), None)
    known = next((c for c in rows if invoice.senderEmail and c.supplier_email == invoice.senderEmail), None)
    return score_invoice(legacy_invoice(invoice), previous, known)["level"].upper()


def load_evaluator(spec: str):
    if spec == "legacy":
        return legacy_evaluator
    module, _, name = spec.partition(":")
    fn = getattr(importlib.import_module(module), name)

    def wrapped(invoice: Invoice, history: list[Invoice]) -> str:
        res = fn(invoice, history)
        level = res.get("riskLevel") or res.get("level") if isinstance(res, dict) else getattr(res, "riskLevel", None)
        return str(level).upper()

    return wrapped


def ratio(num: int, den: int):
    return num / den if den else None


def fmt(x) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=str(DATASET))
    ap.add_argument("--evaluator", default="legacy")
    ap.add_argument("--threshold", default="MEDIUM", choices=LEVELS, help="с какого уровня счёт считается помеченным")
    ap.add_argument("--json", help="сохранить сырые результаты и метрики в файл")
    args = ap.parse_args()

    data = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    histories = {k: [Invoice.model_validate(i) for i in v] for k, v in data["histories"].items()}
    evaluate = load_evaluator(args.evaluator)
    cut = LEVELS.index(args.threshold)

    rows, errors = [], []
    for case in data["cases"]:
        try:
            level = evaluate(Invoice.model_validate(case["invoice"]), histories.get(case["history"], []))
            if level not in LEVELS:
                raise ValueError(f"неизвестный уровень {level!r}")
        except Exception as exc:  # noqa: BLE001 - случай не должен ронять весь прогон
            errors.append({"caseId": case["caseId"], "error": f"{type(exc).__name__}: {exc}"})
            continue
        rows.append({"case": case, "level": level, "flagged": LEVELS.index(level) >= cut})

    def counts(subset):
        tp = sum(r["flagged"] and r["case"]["expected"]["flagged"] for r in subset)
        fp = sum(r["flagged"] and not r["case"]["expected"]["flagged"] for r in subset)
        fn = sum(not r["flagged"] and r["case"]["expected"]["flagged"] for r in subset)
        tn = sum(not r["flagged"] and not r["case"]["expected"]["flagged"] for r in subset)
        return tp, fp, fn, tn

    tp, fp, fn, tn = counts(rows)
    metrics = {"precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn), "fpr": ratio(fp, fp + tn),
               "tp": tp, "fp": fp, "fn": fn, "tn": tn}

    print(f"оценщик: {args.evaluator}; порог: {args.threshold}+; случаев: {len(rows)} из {len(data['cases'])}")
    print(f"TP={tp} FP={fp} FN={fn} TN={tn}")
    print(f"Precision {fmt(metrics['precision'])}   Recall {fmt(metrics['recall'])}   FPR {fmt(metrics['fpr'])}")

    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["case"]["category"]].append(r)
    print("\nпо категориям (верно помечено / ожидалось по метке):")
    for cat, sub in sorted(by_cat.items()):
        a, b, c, d = counts(sub)
        print(f"  {cat:18} верно {a + d}/{len(sub)}   пропущено {c}   ложных тревог {b}")

    for title, pick in (("ПРОПУЩЕНО (ожидали пометку)", lambda r: not r["flagged"] and r["case"]["expected"]["flagged"]),
                        ("ЛОЖНАЯ ТРЕВОГА (пометили нормальный)", lambda r: r["flagged"] and not r["case"]["expected"]["flagged"])):
        bad = [r for r in rows if pick(r)]
        if bad:
            print(f"\n{title}:")
            for r in bad:
                print(f"  {r['case']['caseId']:10} {r['level']:8} {r['case']['description'][:90]}")
    if errors:
        print("\nОШИБКИ ОЦЕНЩИКА (не учтены в метриках):")
        for e in errors:
            print(f"  {e['caseId']}: {e['error']}")

    if args.json:
        out = {"evaluator": args.evaluator, "threshold": args.threshold, "metrics": metrics, "errors": errors,
               "results": [{"caseId": r["case"]["caseId"], "category": r["case"]["category"], "level": r["level"],
                            "flagged": r["flagged"], "expected": r["case"]["expected"]["flagged"]} for r in rows]}
        Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

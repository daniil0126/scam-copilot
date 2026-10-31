# Тестовый набор (dataset/1)

`cases.json` собирается скриптом `build_dataset.py` (не править руками). Формат `Invoice` по `docs/plans/contracts.md` v0.6.

- `histories`: ранее обработанные счета поставщика (ключ из `history` случая; `null` = истории нет).
- `cases[]`: `caseId`, `category` (`normal`, `suspicious`, `duplicate`, `supplier_change`, `unusual_amount`, `insufficient_data`), `description`, `origin` (откуда взят текст), `history`, `invoice`, `expected`.
- `expected.flagged`: должен ли счёт быть помечен (уровень MEDIUM и выше). По нему считаются Precision, Recall, FPR.
- `expected.signals`: типы сигналов, которые ожидаются; справочно, в метрики не входят. Пусто, если подходящего типа в контракте нет (смена реквизитов в тексте).
- `expected.insufficientData`: часть правил должна вернуть `INSUFFICIENT_DATA`.

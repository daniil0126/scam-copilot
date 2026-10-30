# 03. Нормализация и хранилище

**Приоритет:** P0. **Разделы ТЗ:** 3.2, 15.7. **Зависит от:** 01.

## Цель
Единая модель `Invoice` для любого источника (API, страница плательщика) и персистентное хранение с версиями.

## Модель Invoice
`id, invoiceNumber, status, amount, currency, invoiceDate, dueDate, senderName, senderEmail, recipientName, recipientEmail, paymentTerms, items, paymentLinks, createdAt, updatedAt, source`. Любое поле может быть `null`. Исходный payload хранится отдельно (`raw`) для аудита.

## Задачи
- [ ] Нормализатор: сумма как `Decimal` + ISO-валюта, email в lower-case с trim, текст без лишних пробелов, даты в UTC. Недостающее не достраивать.
- [ ] Адаптеры: `from_paypal_api()` и существующий `to_invoice()` страницы плательщика приводят к одной форме.
- [ ] Валидация входа (Pydantic): некорректные суммы и даты помечаются, не роняют обработку.
- [ ] Схема БД (SQLAlchemy, текущая SQLite, миграции Alembic если уже есть, иначе простой init):
  - `accounts` (подключённые PayPal-аккаунты, зашифрованные токены)
  - `invoices` (текущее состояние), `invoice_versions` (хеш содержимого, `raw`, время)
  - `analyses` (версия инвойса, версия движка, score, level, confidence, сигналы JSON, время)
  - `vendors` (история отправителя), `sync_checkpoints`, `sync_logs`, `jobs`, `notifications`, `audit_reports`
- [ ] Изоляция по аккаунту: `account_id` в каждой таблице и во всех запросах.
- [ ] Хеш версии инвойса: ключ идемпотентности (`account_id + invoice_id + content_hash`).
- [ ] История анализов не перезаписывается: новая строка на каждую версию/запуск.

## Файлы
`backend/app/models.py`, `db.py`, новый `normalize.py`, `backend/tests/test_normalize.py`.

## Готово, когда
Один и тот же инвойс из двух источников даёт одинаковую нормализованную форму; повторная запись той же версии не создаёт дублей.

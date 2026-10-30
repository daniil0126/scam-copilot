# Контракты данных и API

**Версия:** 0.2 (Q1 и Q3 закрыты решением владельца продукта; остальное требует одобрения всех четверых). Правила изменений: [team/WORKFLOW.md](team/WORKFLOW.md), раздел 2. Поля только добавляем, не удаляем и не переименовываем.

Основано на текущем коде: `backend/app/paypal.py` (`to_invoice`), `scoring.py` (`score_invoice`), `checks.py` (`run_check`), `models.py` (`Check`), `src/api/types.ts`.

## 0. Что есть сейчас (не ломаем)

| Что | Где | Форма |
|---|---|---|
| Инвойс для фронта | `to_invoice()` | `{number, supplier{name,email,phone}, note, amount(float), currency, dueDate, status}` |
| Результат проверки | `score_invoice()` + `run_check()` | `{id, invoice, checkedAt, level(low/medium/high), score, findings[{id,label,severity}], comparison[], recommendation, evidence[], ai?}` |
| Хранение | таблица `checks` | одна строка на PayPal-инвойс, `result` JSON, при перепроверке строка **перезаписывается** |
| Эндпоинты | `/checks`, `/checks/bulk`, `GET /checks`, `/paypal/invoices`, `/paypal/invoices/{id}`, `/chat` | без авторизации и без `account_id` |

Расхождения с ТЗ, которые закрывают контракты ниже: нет 4 уровней (только 3), нет `confidence`, нет `source` у сигналов, нет версий инвойса и истории анализов, нет аккаунтов, нет `items`, `paymentLinks`, получателя, `invoiceDate`.

**Стратегия совместимости:** старые ответы `/checks` продолжают работать для текущего расширения. Новые поля добавляются рядом. Новые функции живут под новыми эндпоинтами (раздел 5). Старый `level` (`low/medium/high`) остаётся в старых ответах; в новых используется `riskLevel` из 4 значений.

## 1. Invoice (нормализованный)

Любое поле, кроме `id` и `source`, может быть `null`. Недостающее не достраивается.

```python
class Invoice(BaseModel):
    id: str                       # PayPal id (INV2-...) или id из URL страницы
    accountId: str | None         # подключённый PayPal-аккаунт; null только в standalone-режиме (см. раздел 1.1)
    source: Literal["paypal_api", "payer_page", "pdf"]
    invoiceNumber: str | None
    status: str | None            # как вернул PayPal (DRAFT, SENT, PAID, ...), без перевода
    amount: Decimal | None        # в JSON строкой "123.45", не float
    currency: str | None          # ISO 4217, верхний регистр
    invoiceDate: date | None
    dueDate: date | None
    senderName: str | None
    senderEmail: str | None       # lower-case, trim
    senderPhone: str | None
    recipientName: str | None
    recipientEmail: str | None
    paymentTerms: str | None
    items: list[InvoiceItem] | None
    paymentLinks: list[str] | None   # только URL, найденные в данных; по ним не ходим
    note: str | None              # note + memo + terms (как сейчас в to_invoice)
    createdAt: datetime | None    # UTC
    updatedAt: datetime | None    # UTC
    contentHash: str              # sha256 нормализованного содержимого, ключ версии

class InvoiceItem(BaseModel):
    name: str | None
    description: str | None
    quantity: str | None
    unitAmount: str | None
```

**Откуда поля (проверить на реальном ответе Sandbox до реализации, Даниил, задача плана 01):**
- Уже используются в коде: `detail.invoice_number`, `detail.currency_code`, `detail.payment_term.due_date`, `detail.metadata.create_time`, `detail.note/memo/terms_and_conditions`, `invoicer.business_name/name/email_address/phones`, `amount.value/currency_code`, `status`.
- Присутствуют в запросе создания, но их наличие в ответе не проверено: `primary_recipients[].billing_info`, `items[]`, `detail.invoice_date`, `detail.metadata.last_update_time` (или аналог), ссылки на оплату (`links`). Если поля нет, значение `null`.
- Список (`GET /v2/invoicing/invoices`) не отдаёт имя выставителя (см. комментарий в `fetch_invoices`), поэтому имя догружается отдельным запросом.

### 1.1 Режимы работы (решение Q1)

| Режим | Условие | Что доступно |
|---|---|---|
| **Connected** (основной) | PayPal-аккаунт подключён через OAuth, `accountId` обязателен | Полная интеграция: импорт по API, Historical Audit, мониторинг, история поставщиков, дубликаты, Cross-Invoice, алерты, отчёты, точный аудит |
| **Standalone** (ограниченный) | Аккаунт не подключён | Только разовый анализ PDF или веб-страницы инвойса. Без истории, без сравнения с поставщиком, без мониторинга и отчётов. `accountId = null`, результат не пишется в `invoices`/`analyses`, `confidence` не выше `LOW` |

Правила standalone: правила A, C, E и дубликаты возвращают `INSUFFICIENT_DATA` (истории нет), работают только проверки по самому документу (ссылки, формулировки, телефон в тексте, бренд, срок оплаты). В UI прямо написано, что точный аудит требует подключения PayPal. Текущая таблица `checks` обслуживает только этот режим и legacy-экран.

Существующий `to_invoice()` остаётся, как есть, для старых эндпоинтов. Новый `normalize_paypal(raw) -> Invoice` пишется рядом (`backend/app/normalize.py`), парсер страницы плательщика получает `normalize_payer_page(...) -> Invoice`.

## 2. Signal и RiskResult

```python
class Signal(BaseModel):
    type: SignalType              # см. ниже
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    status: Literal["DETECTED", "INSUFFICIENT_DATA"]
    evidence: str                 # конкретные значения; пустой evidence запрещён при DETECTED
    evidenceData: dict            # машиночитаемо: {"current": "...", "historicalAvg": "...", "refInvoiceIds": [...]}
    source: Literal["API", "RULE_ENGINE", "AI"]
    ruleVersion: str

SignalType = Literal[
    "UNUSUAL_AMOUNT", "DUPLICATE_EXACT", "DUPLICATE_POTENTIAL", "DUPLICATE_SIMILAR",
    "SENDER_MISMATCH", "SENDER_NAME_CHANGED", "SUSPICIOUS_LINK", "UNUSUAL_SENDER_ACTIVITY",
    "NEW_SENDER", "BRAND_IMPERSONATION", "PHONE_IN_TEXT", "SCAM_WORDING", "DUE_DATE_ISSUE",
]
```

`NEW_SENDER`, `BRAND_IMPERSONATION`, `PHONE_IN_TEXT`, `SCAM_WORDING`, `DUE_DATE_ISSUE` переносят существующие находки `score_invoice` (`supplier`, `brand`, `phone`, `wording`, `due`), чтобы ничего не терялось. `INSUFFICIENT_DATA` не влияет на score, но попадает в список (Q2).

```python
class RiskResult(BaseModel):
    invoiceId: str
    invoiceVersionHash: str       # contentHash версии, которую оценили
    riskScore: int                # 0..100
    riskLevel: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]   # 0-29 / 30-59 / 60-79 / 80-100
    confidence: Literal["LOW", "MEDIUM", "HIGH"]               # независим от riskScore
    signals: list[Signal]
    recommendations: list[str]
    comparison: list[ComparisonRow]    # как сейчас: {field,current,previous,differs}
    engineVersion: str
    analyzedAt: datetime
    ai: AiExplanation | None

class AiExplanation(BaseModel):
    summary: str
    provider: str
    status: Literal["OK", "UNAVAILABLE"]
```

**Функция Адиля:**

```python
def evaluate(invoice: Invoice, history: VendorHistory, config: RulesConfig) -> RiskResult
```

Чистая функция: без БД, сети и AI. Даниил готовит `history`:

```python
class VendorHistory(BaseModel):
    senderKey: str                           # нормализованный senderEmail, иначе senderName
    priorInvoices: list[HistoricalInvoice]   # другие версии/инвойсы того же отправителя, без текущего
    knownContacts: list[ContactSnapshot]     # {email, name, phone, firstSeen, lastSeen}
    otherSenderInvoices: list[HistoricalInvoice]  # для дубликатов и связей между отправителями
    totalCount: int
    complete: bool                           # False, если история обрезана лимитом

class HistoricalInvoice(BaseModel):
    id: str; invoiceNumber: str | None; amount: str | None; currency: str | None
    createdAt: datetime | None; itemsSignature: str | None   # хеш нормализованных позиций
    senderEmail: str | None; senderName: str | None; paymentLinks: list[str] | None
```

Правило порядка: история содержит только инвойсы, созданные раньше оцениваемого (как «oldest first» в `/checks/bulk`), чтобы повторный прогон давал тот же результат.

## 3. Хранилище (минимум, чтобы не было конфликтов миграций)

Таблицы создаёт только Даниил (план 03). Старая `checks` остаётся для текущего расширения до миграции.

| Таблица | Ключевые поля |
|---|---|
| `accounts` | `id`, `paypalPayerId`, `env`, `encryptedTokens`, `monitoringState`, `createdAt` |
| `invoices` | `(accountId, id)` PK, `currentVersionHash`, `firstSeenAt`, `lastSyncedAt` |
| `invoice_versions` | `(accountId, invoiceId, contentHash)` unique, `normalized` JSON, `raw` JSON, `seenAt` |
| `analyses` | `id`, `(accountId, invoiceId, contentHash)`, `engineVersion`, `result` JSON (RiskResult), `analyzedAt`; строки не перезаписываются |
| `vendors` | `(accountId, senderKey)`, агрегаты, `contactHistory` JSON |
| `sync_checkpoints`, `sync_logs`, `jobs`, `notifications`, `audit_reports` | поля описаны в планах 08, 09, 10, 12 |

Идемпотентность: unique `(accountId, invoiceId, contentHash)` для версий и `(accountId, invoiceId, contentHash, engineVersion)` для анализов; уведомления unique `(accountId, invoiceId, contentHash, eventType)`.

## 4. Общие правила API

- JSON, поля `camelCase`, даты ISO 8601 UTC с `Z`, суммы строками.
- Ошибки: `{"error": {"code": "STRING", "message": "..."}}` с HTTP-статусом; коды: `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `VALIDATION`, `PAYPAL_UNAVAILABLE`, `RATE_LIMITED`, `ANALYSIS_FAILED`.
- Все новые эндпоинты привязаны к аккаунту сессии; `accountId` из тела запроса не принимается (Q3).
- Пагинация: `?cursor=...&limit=...` (max 200), ответ `{items, nextCursor}`.
- Ошибка анализа одного инвойса не ломает список: у элемента `analysisStatus: "FAILED"` и `error`.

## 5. Новые эндпоинты (заглушки с этой формой отдаёт Даниил в первые 2 дня)

| Метод и путь | Назначение | Ответ |
|---|---|---|
| `GET /accounts/me` | статус подключения | `{id, env, connected, monitoring: "ACTIVE"/"PAUSED"/"ERROR", lastSuccessfulSyncAt}` |
| `POST /accounts/connect`, `GET /accounts/callback` | OAuth (план 02) | redirect / `{connected}` |
| `POST /audits` | запуск Historical Audit | body `{period: "7d"/"30d"/"90d"/"custom", from?, to?}` -> `{auditId, status}` |
| `GET /audits/{id}` | прогресс и итог | `{auditId, status, period, progress{total,done,failed,skipped}, summary{low,medium,high,critical,unanalyzed}, startedAt, finishedAt}` |
| `GET /audits/{id}/invoices` | строки таблицы | `{items: [InvoiceRow], nextCursor}` |
| `GET /invoices/{id}` | карточка | `{invoice: Invoice, analysis: RiskResult \| null, analysisStatus, versions: [{contentHash, seenAt}], vendor: VendorSummary}` |
| `GET /invoices/{id}/analyses` | история анализов | `{items: [RiskResult]}` |
| `POST /invoices/{id}/explain` | AI-объяснение и вопросы | body `{question?}` -> `{ai: AiExplanation}` |
| `GET /vendors/{senderKey}` | профиль поставщика | `VendorSummary` |
| `GET /monitoring` | дашборд | `{state, lastSuccessfulSyncAt, totalInvoices, highRisk, criticalRisk, potentialDuplicates, vendorAnomalies, recentEvents[], errors[]}` |
| `POST /monitoring/pause`, `/resume`, `/sync` | управление | `{state}` / `{jobId}` |
| `GET/PUT /monitoring/settings` | пороги алертов | `{alertThreshold, categories{...}}` |
| `GET /notifications`, `POST /notifications/{id}/read` | алерты | `{items: [Notification], unread}` |
| `GET /reports/monthly?month=YYYY-MM` | отчёт | `MonthlyReport` |

```python
class InvoiceRow(BaseModel):
    invoiceId: str; invoiceNumber: str | None; senderName: str | None
    amount: str | None; currency: str | None; invoiceDate: date | None; status: str | None
    riskScore: int | None; riskLevel: str | None; signalTypes: list[str]
    analysisStatus: Literal["ANALYZED", "PENDING", "FAILED", "NOT_ANALYZED"]
    error: str | None

class VendorSummary(BaseModel):
    senderKey: str; invoiceCount: int; totalAmount: dict[str, str]  # по валютам
    averageAmount: dict[str, str]; lastActivityAt: datetime | None
    contactChanges: list[ContactSnapshot]; flaggedInvoiceCount: int

class Notification(BaseModel):
    id: str; invoiceId: str; eventType: str; riskLevel: str
    detectedAt: datetime; signals: list[str]; read: bool; link: str
```

`MonthlyReport` и вспомогательные поля уточняет Руслан в PR с пометкой `contract`; все числа считаются из `analyses`.

## 6. Фикстуры для Дениса, Адиля, Руслана

Даниил кладёт образцы JSON в `backend/tests/fixtures/contracts/` (в этом же PR, что и версия контракта 0.2):
`invoice_minimal.json` (почти все поля `null`), `invoice_full.json`, `risk_result_low.json`, `risk_result_critical.json`, `audit_progress.json`, `invoice_rows_partial.json` (есть FAILED), `monitoring.json`, `notification.json`. Образцы синтетические; в UI-сборку не попадают.

## 7. Открытые вопросы (закрыть до версии 0.2)

- ~~**Q1.**~~ **Закрыт.** Подключённый PayPal-аккаунт обязателен для всех функций с историей. Без него только standalone-анализ PDF/страницы без интеграции (раздел 1.1).
- **Q2.** Показывать ли `INSUFFICIENT_DATA` как сигнал в списке или отдельным полем `dataGaps`? Предложение: сигнал со `status = INSUFFICIENT_DATA`, UI рисует нейтрально.
- ~~**Q3.**~~ **Закрыт: PayPal OAuth подключаем** (раздел 9). Формат сессии и scope уточняются в ADR после проверки документации.
- **Q4.** `PAYPAL_MODE=live` в коде против `production` в ТЗ. Предложение: оставить `live` как есть, в документации писать «live (Production)».
- **Q5.** Миграция старых записей `checks` в `invoices/analyses`: переносим или оставляем как историю старого режима? Предложение: оставить, новые таблицы стартуют пустыми.
- **Q6.** 3 уровня расширения против 4 уровней ТЗ: фронт Дениса переходит на `riskLevel` из 4 значений только в новых экранах; старый экран проверки остаётся на `low/medium/high` до отдельного решения.

## 8. Журнал изменений

| Версия | Дата | Изменение | Автор |
|---|---|---|---|
| 0.1 | 2026-10-30 | Первый черновик на основе текущего кода | Даниил |
| 0.2 | 2026-10-30 | Q1: режимы Connected/Standalone, `accountId` nullable, `source` += `pdf`. Q3: PayPal OAuth, раздел 9 | Даниил |

## 9. Аутентификация (решение Q3)

Подключение через PayPal OAuth 2.0 (authorization code flow, Log in with PayPal), выполняется на backend.

```
Расширение -> POST /accounts/connect          -> {authUrl}
Расширение открывает authUrl (chrome.identity.launchWebAuthFlow или вкладка)
PayPal -> GET /accounts/callback?code&state   -> backend меняет code на токены, шифрует и хранит
Backend -> расширению: сессионный токен backend (не токен PayPal)
```

- Токены PayPal и Client Secret только на backend, зашифрованы в `accounts.encryptedTokens`. В `chrome.storage` лежит лишь сессионный токен backend с ограниченным сроком (порядок: короткоживущий access + refresh), без прав на PayPal.
- Параметр `state` одноразовый и привязан к сессии (защита от CSRF); `redirect_uri` из белого списка в `.env`.
- Каждый запрос к `/accounts/*`, `/audits*`, `/invoices*`, `/vendors*`, `/monitoring*`, `/notifications*`, `/reports*` требует `Authorization: Bearer <session>`; `accountId` берётся из сессии. Чужой ресурс отдаёт `NOT_FOUND`, не `FORBIDDEN`, чтобы не раскрывать существование.
- `/paypal/sandbox/*` остаются только при `PAYPAL_MODE=sandbox`.
- CORS: сейчас разрешён один `chrome-extension://{PROJECT_ID}`, оставляем.
- **Нужно проверить по документации PayPal (Даниил, план 01/02):** какие scope нужны для чтения инвойсов пользователя, поддерживает ли Log in with PayPal нужный scope в Sandbox, нужен ли отдельный app review для Production. Если пользовательский токен не даёт доступ к Invoicing API, откат на токен приложения с привязкой к одному аккаунту фиксируется отдельной ADR; контракт API при этом не меняется.

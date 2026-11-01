# Контракты данных и API

**Версия:** 0.8 (чат читает счета PayPal двумя инструментами: `toolsUsed` в ответе `/chat`, `tools` в `/ai/status`). Ранее 0.7 (описаны уже реализованные эндпоинты уведомлений и отчётов Руслана, таблицы `analyses`, `alert_settings`, `audit_log`). Ранее 0.6 (добавлен `POST /webhooks/paypal`). Ранее 0.5 (добавлены `source = "email"` и `POST /inbound/email`, см. раздел 8; на подтверждение командой в PR с пометкой `contract`). Далее без изменений, версия 0.4: (Q1–Q6 закрыты решением владельца продукта по предложениям из черновика; команде на подтверждение, возражения в PR с пометкой `contract`). Правила изменений: [team/WORKFLOW.md](team/WORKFLOW.md), раздел 2. Поля только добавляем, не удаляем и не переименовываем.

Основано на текущем коде: `backend/app/paypal.py` (`to_invoice`), `scoring.py` (`score_invoice`), `checks.py` (`run_check`), `models.py` (`Check`), `src/api/types.ts`.

## 0. Что есть сейчас (не ломаем)

| Что | Где | Форма |
|---|---|---|
| Инвойс для фронта | `to_invoice()` | `{number, supplier{name,email,phone}, note, amount(float), currency, dueDate, status}` |
| Результат проверки | `score_invoice()` + `run_check()` | `{id, invoice, checkedAt, level(low/medium/high), score, findings[{id,label,severity,detail?,skipped?}], comparison[], recommendation, evidence[], ai?}` |
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
    source: Literal["paypal_api", "payer_page", "email", "pdf"]
    invoiceNumber: str | None
    status: str | None            # как вернул PayPal (DRAFT, SENT, PAID, ...), без перевода
    amount: Decimal | None        # в JSON строкой "123.45", не float
    currency: str | None          # ISO 4217, верхний регистр
    invoiceDate: date | None
    dueDate: date | None
    senderName: str | None
    senderLegalName: str | None   # только payer_page: бизнес за именем «doing business as» (добавлено в 0.4)
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

**Откуда поля.** Проверено 2026-10-30 на одном счёте Sandbox и по схеме Invoicing v2 (см. [adr/001](adr/001-paypal-oauth-and-invoicing-api.md)):
- Есть в детальном ответе `GET /v2/invoicing/invoices/{id}`: `detail.invoice_date`, `detail.metadata.last_update_time`, `invoicer.business_name/name/email_address/phones`, `primary_recipients[].billing_info.email_address`, `items[].id/name/quantity/unit_amount/unit_of_measure`, `detail.metadata.recipient_view_url` и `invoicer_view_url`.
- Не пришли на проверенном счёте (в схеме есть, поэтому остаются `null`, если пусто): `billing_info.name/business_name` (`recipientName`), `detail.note`, `items[].description`.
- `paymentLinks`: берём `recipient_view_url` (страница плательщика PayPal). Отдельной ссылки «оплатить» в ответе не найдено; `links[]` это операции API, в `paymentLinks` не кладём.
- В элементе **списка** нет имени выставителя, телефона, `items`, `last_update_time`; есть `invoice_date`, email получателя и выставителя.
- Уже используются в коде: `detail.invoice_number`, `detail.currency_code`, `detail.payment_term.due_date`, `detail.metadata.create_time`, `detail.note/memo/terms_and_conditions`, `invoicer.business_name/name/email_address/phones`, `amount.value/currency_code`, `status`.
- Если поля нет в ответе, значение `null`; ничего не достраиваем.
- Список (`GET /v2/invoicing/invoices`) не отдаёт имя выставителя (подтверждено), поэтому полные данные догружаются отдельным запросом по каждому счёту.

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
| `invoice_emails` | `rowId` PK, `messageKey` unique, `invoiceId`, `kind` (`new`/`updated`/`unknown`), `template`, `normalized` JSON (Invoice, `source = email`), `links` JSON (хост и признаки, без query), `receivedAt`; HTML письма не хранится. Реализовано в `models.py` (`InvoiceEmail`) |
| `analysis_signals`, `audit_reports`, `notifications`, `alert_settings`, `audit_log` | реализованы Русланом (`reports/models.py`, `notifications/models.py`, `audit_log.py`); `analyses` уже с unique `(account_id, invoice_id, content_hash, engine_version)`. Перенос в `models.py` и миграции не сделаны (согласовать с Даниилом) |
| `sync_checkpoints`, `sync_logs`, `jobs` | поля описаны в планах 08, 09 |

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
| `POST /inbound/email` | письмо PayPal об инвойсе для плательщика (реализовано) | заголовок `X-Inbound-Secret`, тело HTML (`text/html`), без секрета на сервере `503` -> `{stored, duplicate, kind, template, invoiceId, invoice: Invoice, links[{url,text,host,isPaypal,textMismatch}], check: VerificationResult \| null}`; ошибки `401`, `413`, `422` |
| `POST /webhooks/paypal` | событие Invoicing от PayPal (реализовано, только для инвойсов своего аккаунта) | заголовки `PAYPAL-*`, тело события; без `PAYPAL_WEBHOOK_ID` `503`, подпись не прошла `401` -> `{accepted, invoiceId?, reason?}`; из события берётся только id, данные читаются из PayPal |
| `GET /monitoring` | дашборд | `{state, lastSuccessfulSyncAt, totalInvoices, highRisk, criticalRisk, potentialDuplicates, vendorAnomalies, recentEvents[], errors[]}` |
| `POST /monitoring/pause`, `/resume`, `/sync` | управление | `{state}` / `{jobId}` |
| `GET/PUT /monitoring/settings` | пороги алертов | `{alertThreshold, categories{...}}` |
| `GET /notifications?unreadOnly&limit&cursor`, `POST /notifications/{id}/read` | алерты (реализовано) | `{items: [Notification], unread, nextCursor}` |
| | поле `invoice` в `Notification` (добавлено 2026-11-01, только добавление) | `{checkId, number, supplierName, amount, currency, dueDate} \| null` из последней сохранённой проверки счёта; `checkId` открывает проверку в History |
| `GET /notifications/unread-count` | значок в расширении (реализовано) | `{unread}` |
| `GET /reports/monthly?month=YYYY-MM` | последний сохранённый отчёт месяца или расчёт на лету (реализовано) | `MonthlyReport`, `saved: bool` |
| `POST /reports/monthly` | сохранить новую версию отчёта (реализовано) | body `{month}` -> `MonthlyReport` с `version`, `createdAt`; `422` при неверном месяце |
| `GET /monitoring/summary` | счётчики по последнему анализу каждого инвойса (реализовано) | `{invoices, high, critical, potentialDuplicates, vendorAnomalies, recentDetections[{invoiceId, riskLevel, detectedAt}]}` |

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

`MonthlyReport` (реализовано, `backend/app/reports/service.py`): `{month, empty, wording, message?}` для пустого месяца, иначе `{month, empty:false, wording, analyses, invoices, byLevel, potentialDuplicates, vendorAnomalies, suspiciousLinks, topFlaggedSuppliers[{supplierEmail, supplierName, flaggedInvoices}], weeklyTrend[{weekStart, analyses, averageScore, highOrCritical}], manualReview[{invoiceId, riskLevel, riskScore, supplierName, signs[]}]}`; все числа считаются из `analyses`. Нужно подтверждение команды (PR с пометкой `contract`).

### Чат с инструментами PayPal (0.8)
Если выполнены все условия (задан провайдер ИИ, он умеет вызывать инструменты, `paypal_mcp.available()`), `POST /chat` позволяет модели прочитать счета подключённого аккаунта Sandbox. Только чтение, ровно два инструмента (`list_invoices`, `get_invoice`), не более 3 ходов и 4 вызовов на вопрос. Форма запроса не меняется.

| Эндпоинт | Было | Добавлено (необязательное поле) |
|---|---|---|
| `POST /chat` | `{ "reply": str }` | `toolsUsed: string[]`: имена инструментов, которые вернули данные. Поля нет, если инструменты не использовались |
| `GET /ai/status` | `{ "enabled": bool, "provider": str \| null }` | `tools: string[]`: список доступных инструментов. Поля нет, если агент выключен |

Если агент недоступен (нет Node или ключей, модель не поддерживает инструменты, ошибка PayPal или модели), `/chat` отвечает как раньше, без инструментов. Результаты инструментов маскируются (почта, телефон), усекаются и передаются как данные; итоговый ответ проходит те же проверки, что и обычный.

## 6. Фикстуры для Дениса, Адиля, Руслана

Даниил кладёт образцы JSON в `backend/tests/fixtures/contracts/` (в этом же PR, что и версия контракта 0.2):
`invoice_minimal.json` (почти все поля `null`), `invoice_full.json`, `risk_result_low.json`, `risk_result_critical.json`, `audit_progress.json`, `invoice_rows_partial.json` (есть FAILED), `monitoring.json`, `notification.json`. Образцы синтетические; в UI-сборку не попадают.

## 7. Вопросы (все закрыты в 0.3)

- ~~**Q1.**~~ Подключённый PayPal-аккаунт обязателен для всех функций с историей. Без него только standalone-анализ PDF/страницы (раздел 1.1).
- ~~**Q2.**~~ **Закрыт:** `INSUFFICIENT_DATA` остаётся сигналом со `status = INSUFFICIENT_DATA`, в score не входит, UI рисует нейтрально. Отдельного `dataGaps` нет.
- ~~**Q3.**~~ PayPal OAuth подключаем (раздел 9). Оговорка: пользовательский токен для Invoicing API не подтверждён (adr/001), поэтому действует откат на токен приложения до ручной проверки.
- ~~**Q4.**~~ **Закрыт:** `PAYPAL_MODE=live` остаётся как есть, в документации писать «live (Production)».
- ~~**Q5.**~~ **Закрыт:** старые записи `checks` не переносим, они остаются историей старого режима; новые таблицы стартуют пустыми.
- ~~**Q6.**~~ **Закрыт:** новые экраны используют `riskLevel` из 4 значений, старый экран проверки остаётся на `low/medium/high` до отдельного решения.

## 8. Журнал изменений

| Версия | Дата | Изменение | Автор |
|---|---|---|---|
| 0.1 | 2026-10-30 | Первый черновик на основе текущего кода | Даниил |
| 0.2 | 2026-10-30 | Q1: режимы Connected/Standalone, `accountId` nullable, `source` += `pdf`. Q3: PayPal OAuth, раздел 9 | Даниил |
| 0.8 | 2026-11-02 | `POST /chat` += `toolsUsed?`, `GET /ai/status` += `tools?`. Только добавление необязательных полей | Даниил (черновик: Claude) |
| 0.7 | 2026-11-01 | Документированы уже реализованные `GET /notifications` (курсор), `/notifications/unread-count`, `GET/POST /reports/monthly`, `GET /monitoring/summary`; форма `MonthlyReport`; таблицы `analysis_signals`, `alert_settings`, `audit_log`. Только описание кода, поведение не менялось | Даниил (черновик: Claude), код: Руслан |
| 0.6 | 2026-10-31 | Новый эндпоинт `POST /webhooks/paypal`. Только добавление | Даниил (черновик: Claude) |
| 0.5 | 2026-10-31 (дополнено в тот же день: `Finding.detail?`, `Finding.skipped?`, оба необязательные) | `Invoice.source` += `email`. Новый эндпоинт `POST /inbound/email` и таблица `invoice_emails` (письма PayPal плательщику: «Invoice from X», «X updated your invoice»). Только добавление | Даниил (черновик: Claude) |
| 0.4 | 2026-10-30 | `Invoice.senderLegalName` (payer_page: «Invoice issued by X (doing business as Y)»). Только добавление поля | Даниил (черновик: Claude) |
| 0.3 | 2026-10-30 | Q2, Q4, Q5, Q6 закрыты по предложениям. Раздел 1: поля сверены с реальным ответом Sandbox и схемой Invoicing v2, `paymentLinks` = `recipient_view_url`. Раздел 9: оговорка по пользовательскому токену | Даниил (черновик: Claude) |

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
- **Проверено ([adr/001](adr/001-paypal-oauth-and-invoicing-api.md)): пользовательский токен Log in with PayPal не даёт доступ к Invoicing API (scope отклонён, список счетов даёт 403). Действует откат ниже; `/accounts/connect` и `/accounts/callback` отложены.** Исходный текст: какие scope нужны для чтения инвойсов пользователя, поддерживает ли Log in with PayPal нужный scope в Sandbox, нужен ли отдельный app review для Production. Если пользовательский токен не даёт доступ к Invoicing API, откат на токен приложения с привязкой к одному аккаунту фиксируется отдельной ADR; контракт API при этом не меняется.

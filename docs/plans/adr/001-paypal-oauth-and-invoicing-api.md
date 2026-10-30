# ADR 001. PayPal OAuth и Invoicing API: что проверено

Дата: 2026-10-30. Статус: **принято (токен приложения), проверено в Sandbox**. Автор проверки: Claude по просьбе Даниила.

## Вопрос

Даёт ли пользовательский токен (Log in with PayPal) доступ к Invoicing API (`contracts.md`, раздел 9, Q3)?

## Что подтверждено

**Официальная спецификация** `https://developer.paypal.com/api/invoicing/v2/schema.json` (OpenAPI 3.2.0, скачана 2026-10-30):

- `GET /v2/invoicing/invoices`, `GET /v2/invoicing/invoices/{id}`, `POST /v2/invoicing/search-invoices` требуют scope `https://uri.paypal.com/services/invoicing/invoices/read`. Создание, отправка, отмена, платежи, возвраты требуют `.../invoices/readwrite` (для нас не нужны: только анализ).
- Единственный описанный поток авторизации в схеме: `clientCredentials`. Потока `authorizationCode` для Invoicing v2 в спецификации **нет**.
- Перечислены scope: `.../invoicing/invoices/read`, `.../invoices/readwrite`, `.../invoicing/internal`, `https://uri.paypal.com/services/invoicing` (устаревший v1, оставлен для совместимости).

**Sandbox, один запуск** (токен приложения + `GET /v2/invoicing/invoices?page_size=1`):

- Токен `client_credentials` получен (`Bearer`, `expires_in` 32400 c), в нём 27 scope, среди них `https://uri.paypal.com/services/invoicing` и `openid`. Список вернул 200, в аккаунте 55 счетов.
- Токен приложения видит счета аккаунта приложения. Это согласуется с `docs/ROADMAP.md` (чужие счета дают 403).

**Webhooks** (`developer.paypal.com/api/rest/webhooks/event-names/`), события Invoicing: `INVOICING.INVOICE.CREATED`, `.UPDATED`, `.PAID`, `.CANCELLED`, `.REFUNDED`, `.SCHEDULED`. События «отправлен» нет. Проверка подписи в Sandbox не выполнялась.

**Фильтры `search-invoices`** (тело запроса): `recipient_email`, `recipient_*_name`, `invoice_number`, `status[]`, `reference`, `currency_code`, `memo`, `total_amount_range`, `invoice_date_range`, `due_date_range`, `payment_date_range`, `creation_date_range`, `archived`, `fields`. Фильтры по датам есть. Формат по схеме: `creation_date_range` принимает дату-время RFC 3339, `invoice_date_range` и `due_date_range` даты. **Проверено в Sandbox (2026-10-30):** `POST /v2/invoicing/search-invoices` с `creation_date_range.start/end` в виде `YYYY-MM-DDTHH:MM:SSZ` работает: окно 10 лет вернуло все 55 счетов, окно 1 день вернуло 1. Реализовано в `fetch_invoices(created_from, created_to)`.

## Что НЕ подтверждено

- **Даёт ли пользовательский токен доступ к Invoicing API.** Страница списка scope Log in with PayPal не открылась (404 по адресу `/docs/connect-with-paypal/integrate/`). Поиск показал для Log in with PayPal только профильные scope (`openid`, `profile`, `email`, `address`, `phone`, `.../paypalattributes`); invoicing-scope там не найден. Это не доказательство невозможности, это отсутствие подтверждения. Получить пользовательский токен без браузерного входа нельзя, в этой сессии он не получен.
- Нужен ли app review для Production.

## Проверка Log in with PayPal в Sandbox (2026-10-30, Даниил в браузере, скрипт `backend/scripts/lipp_probe.py`)

- Log in with PayPal включён для приложения (Features → Add-on services). В настройках (Manage) список запрашиваемых данных состоит только из профильных атрибутов: Full Name, Email, адрес (улица, город, регион, страна, индекс), статус верификации аккаунта, payer ID. Атрибута, связанного со счетами или Invoicing, в списке нет.
- Return URL `https://localhost:8765/callback` дашборд **не сохранил** («Something went wrong saving the application», error id `01364ee79205c`). Return URL `https://example.com/callback` сохранился. Причина (localhost) выведена по результату, PayPal её не назвал.
- Запрос `scope=openid https://uri.paypal.com/services/invoicing/invoices/read` отклонён страницей входа PayPal: «Looks like this action is not supported … (invalid scope)». **Подтверждено: Log in with PayPal не принимает scope чтения счетов.**
- Контрольный заход `scope=openid email` прошёл: код получен, обмен на токен вернул 200 (есть `refresh_token`, `expires_in` 28800). В выданном токене 17 scope (платежи, подписки, споры, vault, webhooks и др.), **среди них нет ни одного `invoicing`**. `GET /v2/invoicing/invoices` с этим пользовательским токеном вернул **403 `NOT_AUTHORIZED`** («Authorization failed due to insufficient permissions»).

## Вывод для плана

Токен Log in with PayPal **не даёт доступ к Invoicing API** (подтверждено: scope отклонён при входе, а токен с `openid email` получает 403 на список счетов), а в схеме Invoicing v2 описан только `clientCredentials`. Принято: подключение счетов идёт через **токен приложения, привязанный к одному аккаунту** (откат из `contracts.md`, раздел 9). Log in with PayPal можно использовать только для идентификации пользователя (`openid email`), но не для чтения счетов.

Следствия:
- Чужой аккаунт «подключить» через OAuth нельзя; продукт видит счета того аккаунта, чьи ключи лежат в backend `.env`. Для Production это один аккаунт на развёртывание. Подключение произвольных аккаунтов потребовало бы PayPal Partner / third-party permissions (не проверялось, отдельная ADR).
- Контракт API не меняется. Эндпоинты `/accounts/connect` и `/accounts/callback` из `contracts.md` отложены; сессия и `accountId` определяются настройкой backend.
- Заявить честно в README и SUBMISSION.

## Исследование: как PayPal даёт доступ к счетам чужого аккаунта (2026-10-30, по текущей документации)

Единственный официально описанный путь к счетам другого мерчанта: **Partner / multiparty**, а не Log in with PayPal.

1. **Многосторонний Invoicing** (`developer.paypal.com/docs/multiparty/invoicing/integrate/`):
   - «This integration is available to select partners only»: доступен только отобранным партнёрам, самостоятельно не включается.
   - Онбординг мерчанта: `POST /v2/customer/partner-referrals`, в `features` передаются `INVOICE_READ_WRITE` и `ACCESS_MERCHANT_INFORMATION`, `products: EXPRESS_CHECKOUT`; затем `GET /v2/customer/partners/{partner_id}/merchant-integrations/{merchant_id}` отдаёт `primary_email`.
   - Заголовки вызовов: `Authorization: Bearer`, `PayPal-Partner-Attribution-Id: BN-CODE`, `PayPal-Auth-Assertion: <JWT>`.
   - Документирован только **`INVOICE_READ_WRITE`** (чтение и запись). Режима «только чтение» в этой странице нет. Это противоречит принципу ТЗ «никаких изменений инвойсов»: получили бы право записи, которым не пользуемся.
   - Страница описывает создание и отправку счетов; про `list`, `get`, `search` чужого мерчанта прямо не сказано.
2. **`PayPal-Auth-Assertion`** (`developer.paypal.com/api/rest/requests/`): JWT, идентифицирующий мерчанта, `alg: none`, payload `{"iss": "<client_id>", "payer_id": "<merchant payer_id>"}` (рекомендуется `payer_id`, не email). Условие: «you must get consent to act on behalf of a merchant». Страница не говорит, что заголовок только для партнёров, и не описывает 403.
3. **Partner Referrals**: v1 в разделе `deprecated`, замена v2 (`/api/partner-referrals/v2`). Устаревший `INVOICING` в списке прав v1 с `INVOICE_READ_WRITE` одно-к-одному не сопоставлен (в документации нет).
4. **NVP/SOAP «Grant a third party permissions»**: старый ручной механизм (Payments Standard), помечен как legacy, даёт и платежи, и возвраты; для нас не подходит.
5. **Client credentials** (`/api/rest/authentication/`): единственный метод, описанный на странице аутентификации REST; токен приложения с `https://uri.paypal.com/services/invoicing` (подтверждено в Sandbox выше).

**Не подтверждено и не проверялось:** даёт ли Auth-Assertion без партнёрского статуса доступ к `GET /v2/invoicing/invoices` чужого мерчанта; можно ли получить партнёрский статус обычному разработчику (скорее всего нужна заявка в PayPal); есть ли у `INVOICE_READ_WRITE` read-only аналог.

**Вывод.** Для продукта «читать счета подключённого пользователя» нужен партнёрский доступ, который не открывается самостоятельно и требует права записи. До получения такого статуса остаётся принятое решение: токен приложения для одного аккаунта. Это стоит упомянуть в «What's next» без обещаний.

## Остаётся открытым
- Нужен ли app review для Production (по документации: для Log in with PayPal до 7 рабочих дней, нужен только при публикации данных клиентов).
- Third-party permissions (Partner) как путь к подключению чужих аккаунтов: не исследовалось.

## Поля ответа (для `contracts.md`, раздел 1)

Реальный ключевой состав **элемента списка** (Sandbox, 1 счёт): `id`, `status`, `detail.invoice_number`, `detail.invoice_date`, `detail.currency_code`, `detail.payment_term.due_date`, `detail.metadata.create_time`, `detail.viewed_by_recipient`, `detail.group_draft`, `amount.{currency_code,value}`, `due_amount.{currency_code,value}`, `invoicer.email_address`, `primary_recipients[].billing_info.email_address`, `links[]`, `unilateral`.

Отсюда:

Реальный ключевой состав **детального ответа** `GET /v2/invoicing/invoices/{id}` (Sandbox, тот же один счёт; проверен один счёт, поля, которые в нём не заданы, могут появляться у других):

| Поле контракта | Статус |
|---|---|
| `invoiceDate`, `dueDate`, `createdAt`, `updatedAt` (`detail.metadata.last_update_time`), `amount`, `currency`, `status`, `invoiceNumber` | **есть** |
| `senderName` (`invoicer.business_name`, `invoicer.name.*`), `senderEmail`, `senderPhone` (`invoicer.phones[]`) | **есть** (имя только в детальном ответе, не в списке) |
| `recipientEmail` (`primary_recipients[].billing_info.email_address`) | **есть** |
| `items` | **есть**: `id`, `name`, `quantity`, `unit_amount`, `unit_of_measure`. `description` в этом счёте не пришло |
| `recipientName` | **нет** на этом счёте (в схеме `billing_info.name` и `business_name` есть, здесь не заданы) |
| `note` | **нет** на этом счёте (поле `detail.note` в схеме есть, здесь не задано) |
| `paymentLinks` | `detail.metadata.recipient_view_url` = `https://www.sandbox.paypal.com/invoice/p/#<id>` (страница плательщика), `invoicer_view_url` (страница выставителя). Отдельной ссылки «оплатить» в ответе нет. `links[]` содержит только rel `self`, `replace`, `cancel`, `remind`, `record-payment`, `qr-code` (это операции API, не ссылки для плательщика, не использовать) |

Важно: `recipient_view_url` показывает ту самую страницу плательщика, которую читает путь через парсер страницы (`docs/plans/audit.md`). Для Connected-режима страницу читать не нужно, API отдаёт больше полей.

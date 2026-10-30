# Аудит (план 01, шаг 3)

Дата: 2026-10-30. Проверено чтением кода в рабочем дереве; тесты не запускались в этой сессии.

## Парсер страницы плательщика: не сделан

Коммит `4490526` («PayPal page parser…») называется шире, чем содержит. В коде есть только **извлечение ID счёта** из URL и текста страницы:

| Что | Где | Статус |
|---|---|---|
| `extractPayPalInvoiceId(href, pageText)`: полный `INV2-…` или короткий хеш `/invoice/p/#…` | `src/lib/paypalPage.ts` | есть |
| Сообщение `GET_PAYPAL_INVOICE` в content script | `src/content.ts` | есть |
| `getPageInvoiceId()` и `PageCheckCard` | `src/lib/pageInvoice.ts` | есть |
| Определение страницы плательщика (`/invoice/p/`, «Amount due», «Report invoice»), ROADMAP 1.2 | | **нет** |
| Разбор `innerText` в поля (выставитель, сумма, даты, позиции, заметка), 1.3 | | **нет** |
| `POST /checks/page`, 1.4 | `backend/app/checks.py` (есть только `""`, `/bulk`, `GET`) | **нет** |
| Фикстуры текстов страниц, 1.1 | `backend/tests/fixtures/` (только `contracts/`) | **нет** |
| Тесты `extractPayPalInvoiceId` | в `package.json` нет тестового раннера | **нет** |

Следствие: `PageCheckCard` берёт ID со страницы и вызывает `POST /checks {invoice_id}`, а backend читает счёт через `get_invoice`. По `docs/ROADMAP.md` чужой счёт даёт `403 NOT_AUTHORIZED`, то есть путь плательщика на реальном чужом счёте не работает. Задачи 1.1–1.4 в `docs/ROADMAP.md` остаются невыполненными, пометки в `overlap-analysis.md` ("не подтверждено") теперь подтверждены.

Остальное, что нашли попутно:

- `content.ts` содержит `GET_DOM_STRUCTURE` (отдаёт весь `outerHTML`); он нигде не используется в `src` по grep. Кандидат на удаление после проверки.
- `main.py` подключает `stubs_router` только при `CONTRACT_STUBS=1`, как заявлено.

## Что делать

1. Владелец нормализации (Даниил) решает, кто пишет `normalize_payer_page`. Порядок: фикстуры (1.1) → определение страницы (1.2) → разбор (1.3) → `POST /checks/page` (1.4).
2. Добавить тестовый раннер для TS (например vitest) или держать разбор на backend, где `pytest` уже есть. Рекомендация: разбор на backend, в content script оставить только сбор `innerText` и URL.

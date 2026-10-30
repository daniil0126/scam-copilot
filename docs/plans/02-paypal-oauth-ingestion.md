# 02. PayPal OAuth и получение инвойсов

**Приоритет:** P0. **Раздел ТЗ:** 3.1. **Зависит от:** 01.

## Цель
Безопасно получать инвойсы только подключённого аккаунта через Invoicing API (Sandbox/Production).

## Уже готово (не переделывать)
Пагинация (`PAGE_SIZE=100`), лимит числа инвойсов (`MAX_INVOICES=500`, флаг `truncated`), догрузка деталей, `PAYPAL_MODE`, тесты `test_paypal_list.py`. Остаётся ниже.

## Задачи
- [ ] По документации определить, какие методы доступны: `GET /v2/invoicing/invoices` (пагинация), `POST /v2/invoicing/search-invoices` (фильтры, в том числе по дате). Не предполагать поля, которых нет в ответе.
- [ ] OAuth 2.0: определить flow (client credentials vs Log in with PayPal для токена пользователя). Если нужен пользовательский токен: authorization code flow, redirect на backend.
- [ ] Хранение токенов только на backend, шифрованно (ключ в `.env`); в `chrome.storage` токенов нет. Расширение получает только сессию/идентификатор подключения.
- [x] (сделано 2026-10-30, `fetch_invoices(created_from, created_to)`, проверено в Sandbox; фильтр по `creation_date_range`) Расширить `paypal.py`: `search-invoices` с фильтром по датам (для периодов плана 08). Конфиг режима уже есть (`PAYPAL_MODE`, значение `live`; название согласовать, Q4).
- [x] (сделано 2026-10-30, `paypal_request`: 3 попытки, `Retry-After` с потолком 10 с; 5xx повторяется только для чтения) Rate limits: уважать `Retry-After`, exponential backoff с jitter на 429 и 5xx.
- [~] (частично: 401/403/404/429 различаются, формат `{"error":{"code"}}` из `contracts.md` ещё не введён) Ошибки: сейчас все ответы PayPal превращаются в 502; различать 401/403 (статус «Reconnect»), 404, 429, 5xx и недоступность (коды из `contracts.md`, без падения процесса).
- [ ] Не логировать секреты и токены.
- [ ] Только чтение: никаких вызовов send/cancel/pay/update.

## Файлы
`backend/app/paypal.py`, новый `backend/app/oauth.py`, `backend/app/main.py` (эндпоинты connect/callback/status/disconnect), `.env.example`.

## Тесты
Моки HTTP (respx/responses) для: пагинации, 429 с Retry-After, 401, 5xx с повтором, лимита числа инвойсов. Один ручной прогон на Sandbox.

## Готово, когда
Подключение Sandbox-аккаунта и получение списка его инвойсов с пагинацией работает, секретов в логах и в расширении нет.

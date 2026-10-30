# 02. PayPal OAuth и получение инвойсов

**Приоритет:** P0. **Раздел ТЗ:** 3.1. **Зависит от:** 01.

## Цель
Безопасно получать инвойсы только подключённого аккаунта через Invoicing API (Sandbox/Production).

## Задачи
- [ ] По документации определить, какие методы доступны: `GET /v2/invoicing/invoices` (пагинация), `POST /v2/invoicing/search-invoices` (фильтры, в том числе по дате). Не предполагать поля, которых нет в ответе.
- [ ] OAuth 2.0: определить flow (client credentials vs Log in with PayPal для токена пользователя). Если нужен пользовательский токен: authorization code flow, redirect на backend.
- [ ] Хранение токенов только на backend, шифрованно (ключ в `.env`); в `chrome.storage` токенов нет. Расширение получает только сессию/идентификатор подключения.
- [ ] Расширить `paypal.py`: клиент с пагинацией (`page`, `page_size`), лимитом количества инвойсов, конфигом `PAYPAL_ENV=sandbox|production`.
- [ ] Rate limits: уважать `Retry-After`, exponential backoff с jitter на 429 и 5xx.
- [ ] Ошибки: 401/403 (повторная авторизация, понятный статус «Reconnect»), недоступность API (статус, без падения процесса).
- [ ] Не логировать секреты и токены.
- [ ] Только чтение: никаких вызовов send/cancel/pay/update.

## Файлы
`backend/app/paypal.py`, новый `backend/app/oauth.py`, `backend/app/main.py` (эндпоинты connect/callback/status/disconnect), `.env.example`.

## Тесты
Моки HTTP (respx/responses) для: пагинации, 429 с Retry-After, 401, 5xx с повтором, лимита числа инвойсов. Один ручной прогон на Sandbox.

## Готово, когда
Подключение Sandbox-аккаунта и получение списка его инвойсов с пагинацией работает, секретов в логах и в расширении нет.

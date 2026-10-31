# Чеклист безопасности (план 13, этап 1)

Проверено по коду ветки `main` + ветки `feat/13-security-alerts` (`security.py`, `audit_log.py`). Статусы: ✅ есть и подтверждено, ⚠️ есть пробел, ⏳ не реализовано (зависит от другого плана), ❓ не проверялось. Автоматически проверяется то, что в колонке «Тест».

| # | Пункт плана 13 | Статус | Что в коде | Тест | Что делать (владелец) |
|---|---|---|---|---|---|
| 1 | Секреты только на backend, в `.env` | ✅ | `.env`, `*.pem`, `*.db` в `.gitignore`; `.env.example` без значений | ручная проверка | |
| 2 | OAuth 2.0, токены зашифрованы в БД | ⏳ | сейчас client credentials из `.env`, сессий нет | | план 02 (Даниил) |
| 3 | Изоляция по `account_id` | ⚠️ | `monitor.py` везде фильтрует по `account_id()`; `security.current_account()` не берёт аккаунт из запроса. Таблица `checks` (legacy) без `account_id` | нет: аккаунт один, тестировать доступ к чужому нечем | тест «чужой аккаунт» добавить с сессиями (план 02) |
| 4 | Валидация входа и размеры | ⚠️ | текст страницы ограничен (`MAX_TEXT`). `invoice_id` не проверяется: `CheckRequest.invoice_id: str` (`checks.py:23`) уходит в путь `/v2/invoicing/invoices/{invoice_id}` (`paypal.py:197`, `monitor.py:91`) | нет | ограничить `invoice_id` шаблоном `^INV2-[A-Z0-9-]{6,64}$` в `CheckRequest` и `get_invoice` (`paypal.py` Даниил, `checks.py` Адиль) |
| 5 | SSRF: ссылки инвойса не открываем | ✅ | исходящие запросы только на `BASE_URL` PayPal и OpenRouter; ссылки из инвойса (`paymentLinks`, текст) нигде не запрашиваются | `test_security.py::test_outbound_hosts_are_only_paypal_and_openrouter` | пункт 4 закрывает остаток (подмена пути через `invoice_id`) |
| 6 | Подпись webhook | ✅ | `webhooks.py` проверяет через `verify-webhook-signature` PayPal, id берётся только из события | `test_webhooks.py` | |
| 7 | Секреты и токены не попадают в логи | ⚠️ | `security.scrub` и `install_log_scrubber` написаны, но **нигде не вызываются** | `test_security.py::test_scrubber_*` проверяют сам чистильщик | вызвать `install_log_scrubber()` при старте в `main.py` (Даниил) |
| 8 | Минимум ПД в запросах к AI | ✅ | `ai_guard.py`, `llm.py` | `test_llm_injection.py` | |
| 9 | Аудит-лог действий | ❓ | модель и запись есть (`audit_log.py`); подключение к подключению, паузе, ручному sync, смене порогов не проверялось | | проверить вызовы в `monitor.py` (pause/resume/sync) |
| 10 | Никаких платежей, отмен, изменений инвойсов | ⚠️ | записывающие вызовы PayPal: проверка подписи webhook (только проверка), и два **sandbox-маршрута** `POST /sandbox/invoices` и `/sandbox/invoices/{id}/send`, создающие тестовые счета | `test_security.py::test_paypal_writes_are_only_the_known_ones` | убрать sandbox-маршруты из сборки для подачи или оставить под `PAYPAL_MODE=sandbox` (решение команды) |

## Что остаётся открытым
- Пункты 4, 7 требуют правок в чужой зоне (`paypal.py`, `main.py`, `checks.py`): нужен issue или PR владельцу.
- Пункты 2, 3 закрываются планом 02; после него добавить тест доступа к чужому аккаунту.
- Пункт 9: проверить и дописать.

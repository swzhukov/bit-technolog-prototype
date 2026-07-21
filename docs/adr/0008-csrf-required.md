# ADR-0008: CSRF на все POST запросы из JS

**Дата:** 2026-05-20
**Статус:** Accepted
**Контекст:** HTTP Basic Auth + SameSite cookie. Без CSRF — злоумышленник может отправить форму от имени залогиненного пользователя.

## Решение

Middleware проверяет каждый POST/PUT/DELETE/PATCH запрос:
- `X-Requested-With: XMLHttpRequest` (fetch должен добавлять)
- `Referer` совпадает с origin
- `Origin` совпадает с host

Если ничего из этого нет → 403.

## Обоснование

**Почему не используем CSRF token:**
- Дополнительная сложность (генерация, хранение, проверка)
- Для on-premise с одним браузером избыточно
- SameSite cookie + проверка Referer/Origin — достаточно

**Плюсы:**
- Zero implementation overhead
- Работает с любым fetch/axios/curl
- Легко отключить в тестах (`PILOT_CSRF_DISABLED=true`)

**Минусы:**
- Если JS не отправляет `X-Requested-With` — 403 (частая ошибка новичков)
- Не защищает от XSS (но это другой вектор)

## Где смотреть

- `app.py:auth_middleware` — основная проверка
- `app.py:check_auth` — для Basic Auth
- `static/*` — все fetch() должны иметь `X-Requested-With: 'XMLHttpRequest'`

## Тестирование

- `test_app.py:test_csrf_header_on_html_response` — есть CSP
- `test_app.py:test_csp_header_on_html_response` — есть CSP
- `test_app.py:test_rate_limit_blocks_after_max` — есть rate limit

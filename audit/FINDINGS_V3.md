# FINDINGS V3 — Эксплуатационный аудит (глубже V1+V2)

**Дата:** 2026-07-22 21:30
**HEAD:** `93ee103` (после V1+V2)

## V3 подход: операционные проблемы, не покрытые ранее

V1 и V2 покрыли: RBAC, 152-ФЗ, 404, perf, audit. V3 копнул в:
- Operations (port, restart, backup)
- Security headers (HSTS, Secure cookie, CSRF bypass)
- LLM timeout/fallback
- Health check semantics
- Open redirect
- Concurrency / race conditions

## 1. РЕАЛЬНЫЕ (3)

### F3-001. `uvicorn.run(port=8000)` в `__main__` — конфликт портов
- **Файл:** `app.py:1469`
- **Категория:** operations
- **Серьёзность:** MEDIUM
- **Описание:** `if __name__ == "__main__":` запускает uvicorn на **порту 8000**, но systemd ExecStart использует 8081. Если кто-то случайно запустит `python3 app.py`, порт 8000 может конфликтовать с другими сервисами (newton-api использует 8080, но 8000 — это AirPlay default, может быть занят).
- **Fix:** Заменить на 8081 + `--workers 1` + SSL kwargs.

### F3-002. `/health` без timeout — зависнет если БД залочена
- **Файл:** `app.py:1159`
- **Категория:** operations
- **Серьёзность:** MEDIUM
- **Описание:** `db.query_one("SELECT COUNT(*) AS n FROM items")` без timeout. Если БД залочена другой транзакцией, /health подвиснет. systemd/docker health check подумает что сервис healthy, на самом деле нет.
- **Fix:** Обернуть в try/except с timeout, вернуть `db: "error"` если не отвечает за 1 сек.

### F3-003. `session_id` cookie без `Secure` flag
- **Файл:** `app.py:268`
- **Категория:** security
- **Серьёзность:** LOW
- **Описание:** `response.set_cookie("session_id", sid, max_age=7*24*3600, httponly=True, samesite="lax")` — без `secure=True`. На prod TLS есть и есть 308 redirect, но если кто-то зайдёт по HTTP (для отладки), cookie перейдёт в HTTP запросе. Потенциально уязвимо.
- **Fix:** Добавить `secure=True` (cookie только через HTTPS).

## 2. ПРОВЕРЕНО, OK (false alarms)

### F3-FP1. Open redirect через `?next=`
- `next=https://evil.com` → 303 на `/` (игнорируется)
- `next=javascript:alert(1)` → 303 на `/` (защищён)
- Защита работает — `RedirectResponse(url="/")` всегда, не из query

### F3-FP2. API key в логах
- `settings/llm` — api_key_enc зашифровано через Fernet
- `/llm-admin` НЕ показывает `api_key_enc` (только name/display/endpoint/cost/is_active)
- `logger.info/warning/error` — НЕ логирует `api_key` или `api_key_enc`

### F3-FP3. CORS / OPTIONS preflight
- OPTIONS /api/.../update → 405 (Method Not Allowed)
- Нет CORS headers (Same-Origin Policy)
- Защита от CSRF через Origin/Referer в middleware

### F3-FP4. SQL injection
- `?id=1' OR '1'='1` → 000 (curl не парсит)
- Все SQL `?` placeholders (проверено в V1)

### F3-FP5. In-memory state — не баг в пилоте
- `_sessions`, `_rate_limit_buckets` — теряются при рестарте
- В пилотной версии (5 дней, 4 пользователя) — **не проблема**
- В Sprint 6 → Redis

## 3. ПРИОРИТЕТЫ

| # | Severity | Effort | Files |
|---|----------|--------|-------|
| F3-001 | MEDIUM | 1 строка | app.py |
| F3-002 | MEDIUM | 5 строк | app.py |
| F3-003 | LOW | 1 строка | app.py |

**Итого: 7 строк, 1 коммит.**

# FINDINGS V2 — Глубокий аудит (что ПРОПУСТИЛ в прошлом проходе)

**Дата:** 2026-07-22 19:50
**HEAD:** `376ce94` (после M38-final)

## 1. КРИТИЧНЫЕ (152-ФЗ + perf)

### F2-001. **152-ФЗ: ФИО в header на КАЖДОЙ странице**
- **Файл:** `templates/base.html:131`
- **Категория:** 152-ФЗ / privacy
- **Серьёзность:** HIGH
- **Описание:** `current_user.display_name` (Баранов А.Н., Тарлецкий А.С. и т.д.) отображается в header на КАЖДОЙ странице. Любой залогиненный пользователь видит полное ФИО в правом верхнем углу. Я починил приветствие ("Добрый день, коллега"), но ФИО в header всё ещё видно.
- **Скриншот при просмотре /products:** справа сверху "Тарлецкий А.С. (Технолог)".
- **Fix:** Заменить на username (роль) — "tarrietsky (Технолог)"

### F2-002. **152-ФЗ: ФИО утвердившего в публичных списках**
- **Файл:** `templates/knowledge.html:23`, `templates/detail.html:186`
- **Категория:** 152-ФЗ
- **Серьёзность:** MEDIUM
- **Описание:** В списке эталонов показывается `e.approved_by` = ФИО того, кто утвердил. Все залогиненные видят ФИО других.
- **Fix:** Показывать username (tarrietsky) или "—" — не ФИО.

### F2-003. **PERF: /api/change-notices/{id} вызывает LLM на каждый GET**
- **Файл:** `app.py:991` (api_notice)
- **Категория:** perf
- **Серьёзность:** HIGH
- **Описание:** Endpoint делает `generate_ai_diff(notice_id)` на КАЖДОМ GET. 24 сек LLM. Аналог /notices/{id} уже починен в M38-c3, но API endpoint нет.
- **Fix:** Lazy — `ai_diff` генерится только когда клиент запрашивает через `/api/change-notices/{id}/diff` или удалить.

## 2. ВЫСОКИЕ (404 + atomicity)

### F2-004. **/notices/{id}/generate-diff — нет 404 check**
- **Файл:** `app.py:953`
- **Категория:** error-handling
- **Серьёзность:** MEDIUM
- **Описание:** POST /notices/999/generate-diff → 200 + `{"status":"error","detail":"notice not found"}` (не 404).
- **Fix:** Добавить `get_notice(notice_id)` → 404.

### F2-005. **/api/operations/{id}/confirm — нет 404 check**
- **Файл:** `app.py:1201`
- **Категория:** error-handling
- **Серьёзность:** MEDIUM
- **Описание:** POST /api/operations/99999/confirm → 200 + `{"status":"error"}` (не 404).
- **Fix:** Добавить `db.query_one("SELECT id FROM operations WHERE id=?", (operation_id,))` → 404.

### F2-006. **api_approve — нет транзакции (partial state)**
- **Файл:** `app.py:1313`
- **Категория:** reliability
- **Серьёзность:** MEDIUM
- **Описание:** Approve делает 2-3 INSERT/UPDATE: в `etalons` (update or insert), в `tech_cards` (is_approved). Если упадёт между ними — частично утверждено. Audit в `history` тоже не пишется.
- **Fix:** `db.execute("BEGIN")` + `COMMIT`/`ROLLBACK`. И записать в `history` кто утвердил.

## 3. СРЕДНИЕ (operational)

### F2-007. **audit_logins не логирует IP/User-Agent**
- **Файл:** `services/auth.py:168`
- **Категория:** audit
- **Серьёзность:** LOW
- **Описание:** В audit_logins записи имеют `ip=''` и `user_agent=''`. Гляну почему.
- **Проверка:** `SELECT username, ip, user_agent FROM audit_logins WHERE ts > '2026-07-22 16:00'` — все пустые.
- **Fix:** Передать request в функцию `log_audit_login`.

### F2-008. **history table — пустая (0 записей)**
- **Файл:** таблица `history` в БД
- **Категория:** audit
- **Серьёзность:** LOW
- **Описание:** `history` создана в миграции, но **никто не пишет** в неё. Нет audit-trail операций (кто менял ТК, когда).
- **Fix:** В `api_update_operation`, `api_approve`, `notice_resolve` добавить `INSERT INTO history`.

## 4. ИНФРА (защита от регрессий)

### F2-009. **FK без ON DELETE — каскадное удаление опасно**
- **Файл:** `migrations/001_v0_8_init.sql`
- **Категория:** schema
- **Серьёзность:** LOW
- **Описание:** Все FK без `ON DELETE`. В SQLite это означает, что parent нельзя удалить, пока есть child. Это OK для защиты от потерь, но при миграциях/cleanup может зависнуть.
- **Решение:** Оставить как есть (защита важнее). Документировать.

## 5. FALSE POSITIVES (проверено, ОК)

- `/api/change-notices/{id}` — есть 404 ✅
- `/api/operations/{id}/update` — есть 404 ✅
- `/api/tech-cards/.../regenerate` — есть 404 ✅
- `/api/tech-cards/.../approve` — есть 404 ✅
- `/notices/{id}/resolve` — 404 есть (после M38-final) ✅
- Все SQL `?` placeholders — нет SQL injection ✅
- Все 4 роли правильно (RBAC 100% после M38-final) ✅

## ПРИОРИТЕТЫ ФИКСА V2

| # | Severity | Effort | Files |
|---|----------|--------|-------|
| F2-001 | HIGH | 1 строка | base.html |
| F2-002 | MEDIUM | 1 строка × 2 | knowledge.html, detail.html |
| F2-003 | HIGH | 1 строка | app.py |
| F2-004 | MEDIUM | 3 строки | app.py |
| F2-005 | MEDIUM | 3 строки | app.py |
| F2-006 | MEDIUM | 10 строк | app.py |
| F2-007 | LOW | 5 строк | services/auth.py + 2 caller |
| F2-008 | LOW | 5 строк | 3 endpoints |

**Итого: ~30 строк, 1 коммит.**

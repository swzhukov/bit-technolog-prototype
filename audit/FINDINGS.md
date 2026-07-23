# FINDINGS — Полный аудит БИТ.Технолог v1.0.0

**Дата:** 2026-07-22
**Аудитор:** Mavis (полный цикл за один проход)
**HEAD на prod:** `b0cd9e2`

## 1. КРИТИЧНЫЕ (блокируют RBAC — админ не может работать)

### F-001. `api_update_operation` не вызывает `normalize_user_role` → admin получает 403
- **Файл:** `app.py:1219`
- **Категория:** RBAC
- **Серьёзность:** HIGH
- **Описание:** При логине под `techadmin` (в БД role='tech_admin') endpoint возвращает 403. Тот же баг что в M38-c3-fix, но не исправлен в этом endpoint.
- **Проверка:** `curl -b cookies -X POST -H "X-Requested-With: XMLHttpRequest" -H "Content-Type: application/json" -d '{"field":"name","value":"test"}' /api/operations/32/update` → `{"detail":"Недостаточно прав для редактирования"}` HTTP=403
- **Ожидаемо:** 200 (admin может редактировать)
- **Fix:** Добавить `normalize_user_role(user)` сразу после `get_user_from_request`.

### F-002. `api_confirm_operation` не вызывает `normalize_user_role` → admin получает 403
- **Файл:** `app.py:1193`
- **Категория:** RBAC
- **Серьёзность:** HIGH
- **Fix:** Добавить `normalize_user_role(user)`.

### F-003. `api_regenerate` не вызывает `normalize_user_role` → admin получает 403
- **Файл:** `app.py:1282`
- **Категория:** RBAC
- **Серьёзность:** HIGH

### F-004. `api_approve` не вызывает `normalize_user_role` → admin получает 403
- **Файл:** `app.py:1298`
- **Категория:** RBAC
- **Серьёзность:** HIGH

### F-005. `api_process_notice` не вызывает `normalize_user_role` → admin получает 403
- **Файл:** `app.py:1386`
- **Категория:** RBAC
- **Серьёзность:** HIGH

### F-006. `api_export_to_1c` не вызывает `normalize_user_role`
- **Файл:** `app.py:849`
- **Категория:** RBAC
- **Серьёзность:** HIGH (если есть RBAC)

## 2. ВЫСОКИЕ (нет RBAC — workshop_chief может критичные действия)

### F-007. `/notices/{id}/resolve` — нет RBAC
- **Файл:** `app.py:963`
- **Категория:** RBAC
- **Серьёзность:** HIGH
- **Описание:** Workshop_chief может решать извещения (303 redirect). Должно быть только admin/main_tech/tech.
- **Проверка:** POST /notices/1/resolve → 303 для всех 4 ролей (включая workshop_chief)
- **Fix:** Добавить `if user.role not in ("admin", "main_technologist", "technologist"): 403`

### F-008. `/notices/{id}/resolve` — нет 404 check
- **Файл:** `app.py:963-985`
- **Категория:** error-handling
- **Серьёзность:** MEDIUM
- **Описание:** POST /notices/999/resolve → 303 (редирект на `/notices/999`) даже если извещения не существует. Должно быть 404.

### F-009. `/api/change-notices/{id}/process` — нет RBAC
- **Файл:** `app.py:1383`
- **Категория:** RBAC
- **Серьёзность:** HIGH
- **Описание:** Workshop_chief может обработать извещение через API.
- **Проверка:** POST /api/change-notices/1/process → 200 для всех ролей

### F-010. `/api/tech-cards/{id}/regenerate` — нет RBAC
- **Файл:** `app.py:1279`
- **Категория:** RBAC
- **Серьёзность:** HIGH
- **Описание:** Workshop_chief может перегенерировать ТК. Workshop_chief не редактор.

### F-011. `/api/tech-cards/{id}/approve` — нет RBAC
- **Файл:** `app.py:1295`
- **Категория:** RBAC
- **Серьёзность:** HIGH
- **Описание:** Хотя UI скрывает кнопку "Утвердить" для workshop_chief, через API он может утвердить. Дыра в защите.

## 3. СРЕДНИЕ (security/perf)

### F-012. `/api/rs/download/{filename}` — нет RBAC
- **Файл:** `app.py:1107`
- **Категория:** RBAC
- **Серьёзность:** LOW (только XML, не критичные данные)
- **Описание:** Все 4 роли могут скачивать XML РС. Возможно workshop_chief не должен.
- **Решение:** Оставить (XML — это и есть для цеха, нормально).

### F-013. `/notices/{id}/resolve` — нет защиты от уже решённых
- **Файл:** `app.py:963`
- **Категория:** UX
- **Серьёзность:** LOW
- **Описание:** Можно 2 раза подряд решить извещение. UI блокирует, но API нет.

## 4. ИНФРА (для системы)

### F-014. Список endpoints без `normalize_user_role` (потенциальные регрессии)
- `api_update_operation:1219`
- `api_confirm_operation:1193`
- `api_regenerate:1282`
- `api_approve:1298`
- `api_process_notice:1386`
- `api_export_to_1c:849`

**Всего: 6 endpoints требуют фикса.**

### F-015. Workshop_chief может делать всё кроме settings/llm-admin
- Через API можно approve/regenerate/process notices — нужно закрыть.

## 5. FALSE POSITIVES (проверены, ОК)

- 4 роли × 26 GET endpoints: все правильно (200/403/404)
- 4 роли × 15 POST endpoints: основные ОК (после исправления F-001..F-006)
- /notices/1 без LLM: 0.03 сек (после M38-c3)
- /api/rs/download/..%2Fapp.py: 404 (path traversal защищён)
- /api/rs/download/nonexistent.xml: 404
- /api/operations/.../update invalid JSON: 400 (после M38-c4)
- CSRF без XRW/Origin: 403

## 6. ПРИОРИТЕТЫ ФИКСА

| # | Severity | Effort | Order |
|---|----------|--------|-------|
| F-001..F-006 | HIGH | 1 строка × 6 = 6 строк | **1** |
| F-007, F-009, F-010, F-011 | HIGH | 1 проверка × 4 = 4 строки | **2** |
| F-008, F-013 | MEDIUM | 3 строки | **3** |

**Итого: 13 строк кода, 1 коммит.**

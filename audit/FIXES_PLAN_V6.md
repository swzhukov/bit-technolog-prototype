# FIXES_PLAN M38-v6

## Порядок (фундамент → фичи → полировка)

### Модуль 1: 152-ФЗ (CRITICAL)
**Один коммит, потому что всё связано.**

**Действие:**
1. app.py: заменить `user.display_name` → `user.username` в 8 местах:
   - 845, 1044, 1115, 1401, 1527, 1550, 1573, 1603
2. Не трогать `user.display_name` в:
   - НЕ в БД (только в UI: header уже исправлен в M38-v2)
   - НЕ в логировании (если есть)
3. Тест: создать tech_card + notice + resolve → проверить что approved_by/author = "username" а не "ФИО"

### Модуль 2: Тест-раннер (HIGH)
**Один коммит.**

**Действие:**
- В TR.py для каждого RBAC-теста: fresh login для каждого пользователя ПЕРЕД тестом
- Проверить: RBAC-01 и RBAC-05 → 100% pass

### Модуль 3: print() (LOW)
**Один коммит.**

**Действие:**
- services/tp_parser.py:310 — заменить `print(...)` на `logger.debug(...)` или удалить
- grep `print(` во всех services/*.py — нет ли ещё

### Модуль 4: Playwright UI (Sprint 6)
**Отложено.** Для пилота достаточно manual check.

## Порядок коммитов
1. `Fix M38-v6-152: user.display_name → user.username в БД`
2. `Fix M38-v6-test: TR.py fresh login для RBAC`
3. `Fix M38-v6-clean: убрать print() в services`

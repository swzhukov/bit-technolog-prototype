# ПЛАН ФИКСОВ — БИТ.Технолог v1.0.0

**Принцип:** Сначала фундамент (RBAC), потом error handling, потом полировка. Один коммит на группу.

## ГРУППА 1. RBAC (6 endpoints) — КРИТИЧНО

Все 6 endpoints: добавить `normalize_user_role(user)` сразу после `get_user_from_request`, до RBAC check.

- `app.py:849` api_export_to_1c
- `app.py:1193` api_confirm_operation
- `app.py:1219` api_update_operation
- `app.py:1282` api_regenerate
- `app.py:1298` api_approve
- `app.py:1386` api_process_notice

**Проверка после:** `python3 -c "import app; print('OK')"`, прогон POST матрицы → admin получает 200.

## ГРУППА 2. RBAC enforcement (4 endpoints) — ВЫСОКИЙ

Добавить проверку роли в каждом:

- `app.py:963` /notices/{id}/resolve — `if user.role not in ("admin", "main_technologist", "technologist"): 403`
- `app.py:1279` /api/tech-cards/{id}/regenerate — RBAC
- `app.py:1295` /api/tech-cards/{id}/approve — RBAC
- `app.py:1383` /api/change-notices/{id}/process — RBAC

**Проверка:** workshop_chief получает 403.

## ГРУППА 3. 404 + 403 protection

- `app.py:963` /notices/{id}/resolve — добавить `get_notice(notice_id)` → 404

## ПОРЯДОК

1. Worktree: `git worktree add ../bit-technolog-audit -b audit/m38-final main`
2. Внести все 11 правок
3. Прогнать `python -c "import app"`
4. Прогнать e2e_runner.py
5. Прогнать RBAC матрицу
6. Коммит
7. Push + deploy + production tests

## ОЖИДАЕМЫЙ РЕЗУЛЬТАТ

- Admin (techadmin) может делать всё: edit, approve, regenerate, resolve notices
- Workshop_chief (golubev) может только смотреть + approve через UI (но не через API)
- 404 для несуществующих id
- 0 регрессий

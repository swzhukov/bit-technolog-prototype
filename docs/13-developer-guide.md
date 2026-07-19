# Гайд для разработчика — БИТ.Технолог

> **Дата:** 2026-07-19
> **Для кого:** Mavis (AI-ассистент) + любой разработчик, который будет развивать систему после пилота.

---

## 1. Структура проекта

```
/workspace/bit-technolog-prototype/
├── app.py                    # Главный файл (4769 строк, 104 endpoint'а)
├── db.py                     # 22 функции работы с БД (после F15)
├── auth.py                   # 7 функций: ROLES, hash_password, authenticate
├── settings.py               # Fernet encryption + 15 настроек
├── notify.py                 # 3 функции: send_email, send_telegram, notify_workflow
├── llm.py                    # 5 функций: get_llm_client, parse_llm_json, log_llm_call
├── economics.py              # calc_cost_estimate (process-based pricing)
├── learning.py               # get_learning_metrics_by_week (RAG-learning)
├── metrics_auto.py           # 5 функций: compute_acceptance_from_versions
├── rag.py                    # TF-IDF + pymorphy2 + синонимы (F16.2)
├── importers.py              # Excel/PDF/JSON/Word + drawings
├── few_shot.py               # 3 примера + get_relevant_few_shot
├── pilot_report.py           # Markdown + 4 matplotlib charts
├── techinkom_seed.py         # 15 Техинком details
├── test_app.py               # 225 тестов
├── templates/                # Jinja2 templates (26 файлов)
├── static/                   # htmx, qrcode, style.css
├── docs/                     # 12+ документации
├── MISTAKES.md               # 12+ задокументированных ошибок
├── CHANGELOG.md              # История релизов
├── AUDIT_v1.md - AUDIT_v6.md # Результаты аудитов
└── .env, .master_key, .rag/, bit_technolog.db
```

---

## 2. Как добавить новый endpoint

### Пример: добавить `/api/details/{id}/clone` (клонирование детали)

1. **Определить endpoint в `app.py`:**
```python
@app.post("/api/details/{detail_id}/clone")
async def api_clone_detail(request: Request, detail_id: str):
    # 1. Проверка прав (если нужно)
    if get_current_role(request) not in ('technologist', 'main_technologist', 'admin'):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    # 2. CSRF (уже работает middleware)
    # 3. Rate limit (если критичный — добавить в RATE_LIMITS)
    # 4. Бизнес-логика
    from db import get_conn
    conn = get_conn()
    src = conn.execute("SELECT * FROM details WHERE id=?", (detail_id,)).fetchone()
    if not src:
        conn.close()
        return err("not found", 404)
    new_id = f"{detail_id}-copy-{int(time.time())}"
    conn.execute("""INSERT INTO details (id, designation, name, ...)
        SELECT ?, designation || ' (copy)', name, ... FROM details WHERE id=?""",
        (new_id, detail_id))
    conn.commit()
    conn.close()
    # 5. История
    add_history(new_id, "cloned_from", {"src": detail_id})
    # 6. Возврат
    return JSONResponse({"ok": True, "new_id": new_id, "src": detail_id})
```

2. **Добавить тест в `test_app.py`:**
```python
def test_clone_detail(client):
    c, _ = client
    # Создаём source
    c.post("/api/details", data={"id": "src-1", "designation": "X.001", "name": "X"})
    # Клонируем
    r = c.post("/api/details/src-1/clone", data={})
    assert r.status_code == 200
    new_id = r.json()["new_id"]
    # Проверяем что новая деталь существует
    assert c.get(f"/detail/{new_id}").status_code == 200
```

3. **Если нужен UI — добавить кнопку в `templates/detail.html`:**
```html
<button hx-post="/api/details/{{ detail.id }}/clone"
        hx-on::after-request="showToast('Клонировано', 'success')">
    📋 Клонировать
</button>
```

4. **Обновить docs/ если меняется workflow.**

---

## 3. Как добавить новую роль

### Пример: добавить роль `constructor_chief` (гл. конструктор)

1. **Добавить в `auth.py → ROLES`:**
```python
ROLES = {
    # ...existing...
    "constructor_chief": {
        "name": "Гл. конструктор",
        "default_view": "blueprints_approval",
        "can_edit": True,
        "can_approve": True,    # утверждает чертежи
        "can_manage_workflow": True
    }
}
```

2. **Добавить в темплейт role switcher (`templates/base.html`):**
```html
<option value="constructor_chief">🏗 Гл. конструктор</option>
```

3. **В `ROLE_NAMES` для тоста (если используешь showToast):**
```html
ROLE_NAMES = {
    # ...
    constructor_chief: 'Гл. конструктор'
}
```

4. **В conditional buttons (`templates/detail.html`):**
```html
{% if cur_role in ('constructor_chief', 'main_technologist', 'admin') %}
<button>🏗 Утвердить чертёж</button>
{% endif %}
```

5. **Добавить тест:**
```python
def test_constructor_chief_role(client):
    # Создать пользователя с новой ролью через /admin/users/create
    r = c.post("/api/admin/users/create",
               data={"username": "chief", "password": "secret123",
                     "role": "constructor_chief", "display_name": "Гл. конструктор"})
    assert r.status_code == 200
```

---

## 4. Как добавить новую настройку в /admin/settings

1. **Добавить в `settings.py → SETTING_REGISTRY`:**
```python
SETTING_REGISTRY = [
    # ...existing...
    ("NEW_SETTING_KEY", "int", "100", "Описание настройки", False),
]
# Формат: (key, type, default, description, is_secret)
```

2. **Использовать через `get_setting`:**
```python
from settings import get_setting
value = get_setting("NEW_SETTING_KEY", "100")  # default если не задан
```

3. **UI автоматически появится в `/admin/settings`** (группы: LLM/Telegram/SMTP/Лимиты).

---

## 5. Как добавить новый импорт (Excel/PDF/JSON/Word)

В `importers.py`:
```python
def import_from_my_format(file_path: str) -> list[dict]:
    """Импорт из моего формата.
    Возвращает список dict'ов для insert в details."""
    # ... парсинг ...
    return [{"id": ..., "designation": ..., ...}]
```

В `app.py` (`/api/import/tk`):
```python
# Добавить if-ветку по расширению
if filename.endswith('.myfmt'):
    rows = import_from_my_format(filepath)
```

**Не забыть magic bytes** — без них .exe переименованный в .pdf пройдёт.

---

## 6. Как добавить новую метрику в /pilot/learning

1. **Записать в `pilot_metrics` (в нужном месте):**
```python
record_metric(detail_id, "new_metric", value, {"extra": "data"})
```

2. **В `learning.py → get_learning_metrics_by_week`** добавить SQL:
```python
new_metric = conn.execute("""SELECT AVG(value) FROM pilot_metrics
    WHERE metric='new_metric' AND date(created_at) >= ? AND date(created_at) < ?""",
    (ws, we)).fetchone()[0] or 0
```

3. **В `templates/pilot_learning.html`** добавить поле в week-card.

---

## 7. Тестирование

```bash
# Все тесты
PILOT_AUTH_DISABLED=true python -m pytest test_app.py -v

# Конкретный тест
PILOT_AUTH_DISABLED=true python -m pytest test_app.py::test_name -v

# С coverage (после pip install pytest-cov)
PILOT_AUTH_DISABLED=true python -m pytest test_app.py --cov=. --cov-report=term-missing
```

---

## 8. Deploy

```bash
# 1. Локально: проверить что тесты проходят
PILOT_AUTH_DISABLED=true python -m pytest test_app.py

# 2. Commit + push
git add -A
git commit -m "..."
git push origin main

# 3. На production (требуется SSH ключ)
ssh root@seefeesnahurid.beget.app
cd /opt/beget/bit-technolog
git pull origin main
systemctl restart bit-technolog
sleep 4
curl http://127.0.0.1:8081/health
```

### Откат
```bash
ssh root@seefeesnahurid.beget.app
cd /opt/beget/bit-technolog
git log --oneline -5
git checkout <commit>  # откат
systemctl restart bit-technolog
```

---

## 9. Стиль кода

- Python 3.12, type hints где возможно
- Docstrings для всех публичных функций
- f-strings (не .format() или %)
- 4 пробела отступ
- Максимум 100 строк на функцию (если больше — refactor)
- DRY: выносить в модули если >2 использований

---

## 10. MISTAKES.md (важно!)

Каждая ошибка → запись в `MISTAKES.md`:
- M1-M12 (закрыты)
- M13-M14 (открыты — refactor app.py, admin.py)

**Перед коммитом** прочитай `MISTAKES.md` и убедись что не повторяешь старые ошибки.

---

## 11. Что НЕ делать

- ❌ Не использовать `eval()` или `exec()`
- ❌ Не хранить пароли в открытом виде
- ❌ Не делать SQL через f-strings (только `?` placeholders)
- ❌ Не возвращать 500 без понятного сообщения
- ❌ Не удалять миграции из `init_db` (только добавлять)
- ❌ Не отключать CSRF/Rate limit без `PILOT_CSRF_DISABLED=true` / `PILOT_RATELIMIT_DISABLED=true`
- ❌ Не коммитить .env, .master_key, bit_technolog.db (в .gitignore)
- ❌ Не делать `git push --force` на main
- ❌ Не менять структуру БД без миграции (V6-4 — alembic-lite)
- ❌ Не ломать существующие endpoint'ы без обратной совместимости

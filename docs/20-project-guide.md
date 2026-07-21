# PROJECT_GUIDE — карта БИТ.Технолог

> Написано Mavis 2026-07-21 на основе анализа 1069-узлового knowledge graph проекта.
> Цель: за 5 минут понять, что в проекте есть и куда смотреть.

## Что это за проект

**БИТ.Технолог** — AI-помощник технолога на ООО «ПК Техинком-Центр» (пожарные автоцистерны, подъёмники).

**Workflow (от детали до ТК):**
1. Технолог получает обозначение детали (ЛМША.301314.010, 53-ТВ.05.00.00)
2. Заполняет свойства (материал, масса, шасси)
3. Опционально загружает чертёж (PDF/DXF) — AI распознаёт поля
4. Жмёт "Сгенерировать ТК"
5. AI выдаёт черновик: операции, оборудование, время, уверенность
6. Технолог правит 1-2 операции inline, утверждает
7. ТК уходит в 1С:ERP (XML экспорт) и в Telegram гл. технологу

**Что есть (high-level):**
- 11 деталей в БД (тестовые)
- 234 единиц оборудования (27 — реальных Техинкома, 207 — из 1С)
- 5 цехов с 36 операциями Техинкома
- 22 Python файла, 13 331 строк кода
- 35 HTML templates (Jinja2)
- 38 markdown документов
- 272 теста (все passing)

---

## Главные модули (community hubs по графу)

| Файл | Что делает | Когда туда лезть |
|------|------------|------------------|
| **`app.py`** (5000+ строк) | Главный бэкенд. Все endpoints, middleware, lifespan, prompts, роутинг. | Нужно **всегда** — это ядро |
| `db.py` | SQLite-таблицы, миграции, seeds. Все 20+ таблиц (details, drafts, equipment, materials, professions, drawings, history, llm_calls, pilot_metrics, audit_logins, step_answers, deleted_operations, rules, iot, benchmarks, resource_specs, app_settings). | Хочу добавить/изменить таблицу |
| `rag.py` | RAG через TF-IDF (scikit-learn). Лемматизация pymorphy2 + синонимы для русского. | Хочу улучшить поиск похожих ТК |
| `llm.py` | YandexGPT-клиент, логирование вызовов, расчёт стоимости. | Хочу сменить LLM-провайдера |
| `admin.py` | Админка: пользователи, роли, логи входов, настройки, LLM-вызовы, errors, system, backup, RAG. | Задача про admin/управление |
| `auth.py` | HTTP Basic Auth, CSRF, rate limiting, security headers. | Меняю авторизацию |
| `economics.py` | Process-based pricing (CADDi-стиль): раскладка по этапам маршрута. | Меняю расчёт стоимости ТК |
| `learning.py` | Сбор метрик с пилота (sessions, time-to-card, edits, acceptance). | Задача про метрики/обучение |
| `drawing_recognize.py` | OCR чертежей (PDF/PNG/JPG) → поля. pdftoppm + tesseract rus+eng. | Меняю распознавание |
| `workshops_tehinkom.py` | Реальные цеха + операции Техинкома. Подаётся в LLM system prompt. | Обновляю цеха |
| `prompts.py` | System prompts: WELDING, ELECTRICAL, HYDRAULIC, PAINT, TECH_CARD, CLARIFICATION, REFINE. | Меняю промты для AI |
| `few_shot.py` | Примеры ТК для LLM (few-shot). | Меняю примеры |
| `equipment.json` / `structure.json` | Hardcoded справочник оборудования + структура предприятия. | Добавляю оборудование |
| `pilot_report.py` | PDF/Markdown отчёт по пилоту. matplotlib. | Готовлю отчёт руководству |
| `importers.py` | Импорт ТК из 1С. | Задача про миграцию данных |
| `notify.py` | Telegram/SMTP уведомления. | Меняю нотификации |
| `settings.py` | Глобальные настройки (Fernet-encrypted). | Меняю дефолты |

---

## Workflow технолога (что в коде делает каждый шаг)

| UI кнопка | Endpoint | Что в коде |
|-----------|----------|------------|
| "Сгенерировать ТК" (главная CTA) | `POST /api/draft-fast` → `POST /generate` (HTMX) | `app.py:api_draft_fast` + `app.py:generate()` — собирает `properties`, `equipment`, `structure`, `workshops_context`, `few_shot`, `rules` → подставляет в `TECH_CARD_PROMPT` → вызывает `llm.py` → `save_draft()` в БД |
| "Утвердить" | `POST /api/approve/{id}` | `app.py:approve()` → `UPDATE drafts SET status='approved'` + `rag.rag_index_detail()` для RAG |
| Inline-edit операции | `POST /api/operations/{id}/edit` | `app.py:api_edit_operation()` → `UPDATE drafts SET llm_output=...` + history |
| Чертёж → "Распознать" | `POST /api/drawing/recognize` | `app.py:api_drawing_recognize()` → `drawing_recognize.recognize_drawing()` → `pdftoppm` + `tesseract` + regex |
| "Применить к детали" | `POST /api/details/{id}/apply-ocr` | `app.py:api_apply_ocr()` → `UPDATE details` с распознанными полями |
| Экономика | `POST /api/details/{id}/economics` | `app.py:api_save_economics()` → `UPDATE details` cost_per_hour/overhead/material |

---

## Workflow пилота

| Этап | Endpoint | Что делает |
|------|----------|------------|
| Старт сессии | `POST /api/pilot/session/start` | `app.py:api_pilot_session_start()` → `INSERT pilot_metrics` + `record_session_start()` |
| Согласование workflow | `POST /api/workflow/assign` | `app.py:api_workflow_assign()` — главный → нач. цеха |
| Завершение | `POST /api/pilot/session/end` | `app.py:api_pilot_session_end()` → метрики |
| Отчёт | `GET /pilot/report` | `app.py:generate_pilot_report()` → `pilot_report.py` → PDF + MD |

---

## Структура БД (только важное)

- **`details`** — детали (designation, material, mass_kg, drawing_path, parent_id, level)
- **`drafts`** — черновики ТК (detail_id, llm_output JSON, status: new/draft/approved)
- **`draft_versions`** — история версий draft'а (для сравнения)
- **`edits`** — что правил технолог (для learning)
- **`equipment`** — 234 единиц (source: 1c или tehinkom_docx_2025)
- **`materials`** — справочник материалов
- **`professions`** — профессии (19905 Сварщик и т.д.)
- **`departments`** — цеха
- **`drawings`** — загруженные файлы
- **`resource_specs`** — РС для экспорта в 1С
- **`history`** — лог всех действий
- **`pilot_metrics`** — метрики пилота
- **`llm_calls`** — все вызовы LLM (модель, токены, стоимость)
- **`app_settings`** — глобальные настройки (Fernet-encrypted)
- **`rules`** — правила технолога для RAG
- **`step_answers`** — backup для 3-step flow (LS)
- **`deleted_operations`** — soft-delete операций
- **`benchmarks`** — метрики по этапам

---

## 5 типичных задач и куда смотреть

**"Добавить новое поле в форму детали"**
→ `templates/detail_form.html` (UI)
→ `templates/detail.html` (отображение)
→ `app.py:api_update_detail_*` (если есть)
→ `db.py:CREATE TABLE details` (если новая колонка — ALTER TABLE)

**"Изменить логику утверждения ТК"**
→ `app.py:approve()` (там `UPDATE drafts SET status='approved'`)
→ `templates/detail.html` (кнопка)
→ `docs/14-roles-user-guide.md` (роли)

**"Подключить новый LLM-провайдер"**
→ `llm.py` (основной клиент)
→ `.env` (LLM_API_KEY, LLM_MODEL, LLM_API_URL)
→ `app.py:settings.get_setting("LLM_API_KEY")` (использование)
→ `admin.py:api_admin_set_setting` (через UI)

**"Улучшить промт"**
→ `prompts.py` (5 типов: WELDING, ELECTRICAL, HYDRAULIC, PAINT, TECH_CARD)
→ `workshops_tehinkom.py` (контекст реальных цехов)
→ `few_shot.py` (примеры)
→ Тесты: `test_specialized_prompts_*`

**"Добавить endpoint для новой фичи"**
→ `app.py` (новый `@app.post(...)` или `@app.get(...)`)
→ `templates/*.html` (UI через HTMX)
→ `static/design-system.css` (стили — CSS variables, BEM)
→ `test_app.py` (тест)

---

## Подводные камни (из MISTAKES.md)

1. **CSRF обязателен** для всех POST fetch в JS (`X-Requested-With: XMLHttpRequest`)
2. **DB_PATH** в production относительный — `os.path.dirname(DB_PATH) or "."`
3. **Парсер DOCX workshops**: workshop name может быть в cell[0] или cell[1] — учитывай оба
4. **PDF — скан**: `pdftotext` пустой, нужен `tesseract -l rus+eng`
5. **На Beget нет pdftoppm/tesseract по умолчанию** — `apt install poppler-utils tesseract-ocr-rus`
6. **`{% if %}` баланс** в Jinja: scripts с функциями НЕ внутри `{% if %}` (иначе ReferenceError)
7. **Race condition** в тестах с cookie — `c.post("/api/role/switch")` в начале
8. **Lazy `_get_templates_db_path_roles()`** — распаковывай tuple правильно
9. **Inline styles** запрещены (M22) — только CSS variables
10. **Перед большим UI-рефактором** — опиши workflow словами, потом рисуй

---

## Тесты

- 272/272 passing
- Запуск: `./venv/bin/pytest test_app.py -x`
- Что покрыто: endpoints, RBAC, CSRF, RAG, OCR, экономика, пилот-метрики, security
- Что не покрыто: e2e (открыть браузер)

---

## Где смотреть полную документацию

- `docs/01-product-design.md` — что это
- `docs/02-architecture.md` — архитектура
- `docs/05-techinkom-context.md` — контекст Техинкома
- `docs/11-tehnolog-guide.md` — для технолога
- `docs/12-admin-guide.md` — для админа
- `docs/15-api-reference.md` — все endpoints
- `docs/16-database-schema.md` — все таблицы
- `docs/17-deployment.md` — деплой на Beget
- `MISTAKES.md` — все баги и уроки
- `graphify-out/GRAPH_REPORT.md` — auto-generated обзор community

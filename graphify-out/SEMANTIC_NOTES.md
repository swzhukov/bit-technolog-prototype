# SEMANTIC_NOTES v2 — обогащение knowledge graph (полная версия)

> **265 community, 1926 nodes, 3100 edges**
> Обновлено: 2026-07-21 (M30)

**Назначение:** Самодостаточный документ, который **заменяет необходимость читать 22 Python файла** для понимания архитектуры. LLM может анализировать проект только по этому файлу + ADR (9 файлов).

**Формат:**
- `C{n}` — community ID в graph.json
- `{N} nodes` — размер community
- `{name}` — hub-имя (наиболее связанный узел)
- `Описание` — что это, зачем, когда смотреть

---

## 1. Python community (код приложения)

**Всего:** 25 community

### C3: `err` (69 nodes)

**Файл:** `app.py`
**Hub:** `get_llm_client()`

Единый helper для ошибок

JSONResponse с status_code. Используется всеми endpoints для консистентного формата ошибок.

**Содержит:** `get_llm_client()`, `parse_llm_json()`, `err()`, `JSONResponse`, `api_workflow_assign()`

---

### C2: `app.py` (65 nodes)

**Файл:** `app.py`
**Hub:** `app.py`

Главный бэкенд (5000+ строк)

Все endpoints, middleware, lifespan, роутинг. Сердце FastAPI. Содержит prompts, OCR, workflow.

**Содержит:** `app.py`, `login_page()`, `_xml_escape()`, `api_1c_export_rs()`, `get_all_details()`

---

### C4: `get_conn` (62 nodes)

**Файл:** `app.py`
**Hub:** `cleanup_old_records()`

Подключение к SQLite (WAL mode)

db.py:15. Все обращения к БД. WAL mode, autocommit off, foreign keys on.

**Содержит:** `cleanup_old_records()`, `api_load_answers()`, `api_workflow_queue()`, `api_import_benchmarks()`, `api_equipment_local_params()`

---

### C5: `admin.py` (50 nodes)

**Файл:** `admin.py`
**Hub:** `admin.py`

Админка (538 строк)

Все endpoints /admin/*: пользователи, роли, логи, настройки, LLM-вызовы, errors, system, backup, RAG. CSRF + Basic Auth.

**Содержит:** `admin.py`, `_get_templates_db_path_roles()`, `admin_dashboard()`, `Request`, `admin_users()`

---

### C8: `Request` (41 nodes)

**Hub:** `Request`

Функция/утилита: Request

**Содержит:** `Request`, `api_save_answers()`, `rate_limit_middleware()`, `server_error_handler()`, `admin_errors()`

---

### C11: `notify_workflow` (38 nodes)

**Файл:** `app.py`
**Hub:** `send_email()`

Telegram уведомления

notify.py — отправка при workflow assign, approve.

**Содержит:** `send_email()`, `send_telegram()`, `notify_workflow()`, `_get_or_create_master_key()`, `_fernet()`

---

### C6: `rag.py` (33 nodes)

**Файл:** `rag.py`
**Hub:** `rag.py`

RAG через TF-IDF (407 строк)

On-prem retrieval: TfidfVectorizer + cosine + лемматизация pymorphy2 + словарь синонимов (Ст3↔сталь3, MIG↔полуавтсварка). Индекс в .rag/.

**Содержит:** `rag.py`, `_get_morph()`, `_apply_synonyms()`, `_lemmatize_text()`, `_ensure_index_dir()`

---

### C15: `save_draft` (29 nodes)

**Файл:** `app.py`
**Hub:** `get_detail()`

Сохранение черновика

db.py:save_draft + versions. JSON в llm_output. M27 fix: api_draft_fast ОБЯЗАН вызывать save_draft().

**Содержит:** `get_detail()`, `save_version()`, `get_versions()`, `record_edit()`, `get_draft()`

---

### C12: `datetime` (21 nodes)

**Файл:** `app.py`
**Hub:** `now_msk()`

Функция/утилита: now_msk()

**Содержит:** `now_msk()`, `datetime`, `api_pilot_session_start()`, `pilot_learning_dashboard()`, `api_pilot_learning()`

---

### C10: `check_auth` (21 nodes)

**Файл:** `app.py`
**Hub:** `check_auth()`

Функция/утилита: check_auth()

**Содержит:** `check_auth()`, `auth_middleware()`, `verify_password()`, `authenticate_pilot_user()`, `log_login()`

---

### C9: `api_import_tk` (20 nodes)

**Файл:** `app.py`
**Hub:** `api_import_tk()`

Импорт ТК из 1С

POST /api/import/tk — принимает Excel/CSV.

**Содержит:** `api_import_tk()`, `Импорт техкарт. Content-Type: applica...`, `importers.py`, `import_from_json()`, `import_from_excel()`

---

### C7: `api_refine` (19 nodes)

**Файл:** `app.py`
**Hub:** `_daily_cost_global()`

Доработка ТК (M25)

POST /api/refine — уточнение draft через LLM с ответами технолога.

**Содержит:** `_daily_cost_global()`, `add_daily_cost()`, `check_daily_limit_or_warn()`, `get_setting()`, `get_daily_cost()`

---

### C14: `recognize_drawing` (16 nodes)

**Файл:** `drawing_recognize.py`
**Hub:** `drawing_recognize.py`

M28 OCR чертежей

Endpoint /api/drawing/recognize. Применяет к детали через /api/details/{id}/apply-ocr.

**Содержит:** `drawing_recognize.py`, `_ocr_image()`, `_pdf_to_text()`, `_image_to_text()`, `recognize_drawing()`

---

### C19: `check_all_roles.py` (14 nodes)

**Файл:** `check_all_roles.py`
**Hub:** `check_all_roles.py`

CLI для проверки ролей

Ручная проверка ролевого UI. Не production.

**Содержит:** `check_all_roles.py`, `extract_badge()`, `extract_visible_admin()`, `extract_ai_block()`, `extract_approve_button()`

---

### C20: `generate_pilot_report` (12 nodes)

**Файл:** `app.py`
**Hub:** `pilot_report_page()`

PDF/MD отчёт пилота

pilot_report.py — matplotlib + markdown. /pilot/report.

**Содержит:** `pilot_report_page()`, `api_pilot_report_markdown()`, `Страница отчёта для руководства`, `Pilot report как Markdown (для копиро...`, `pilot_report.py`

---

### C31: `safe_call` (11 nodes)

**Файл:** `app.py`
**Hub:** `safe_call()`

Try/except обёртка

safe_call(name, fn, *args, default=None) — log.exception + default.

**Содержит:** `safe_call()`, `NC5 fix: вызов с автологированием оши...`, `test_safe_call_logs_exceptions()`, `test_safe_call_returns_value()`, `test_safe_call_returns_default_on_exc...`

---

### C23: `main` (11 nodes)

**Файл:** `e2e_technologist.py`
**Hub:** `e2e_technologist.py`

Функция/утилита: e2e_technologist.py

**Содержит:** `e2e_technologist.py`, `TechnologistDiary`, `.__init__()`, `.log()`, `.note()`

---

### C21: `seed_techinkom_data` (8 nodes)

**Файл:** `app.py`
**Hub:** `_lifespan()`

Начальные данные

init_db() заполняет equipment, materials, professions, departments.

**Содержит:** `_lifespan()`, `init_db()`, `_seed_professions()`, `seed_initial_data()`, `FastAPI lifespan: инициализация БД пр...`

---

### C27: `_check_rate_limit` (8 nodes)

**Файл:** `app.py`
**Hub:** `_check_rate_limit()`

Rate limit middleware

100 req/min на IP для /api/*.

**Содержит:** `_check_rate_limit()`, `F16.10: V3-3 — проверка rate limit.  ...`, `test_rate_limit_no_limit_for_static()`, `test_rate_limit_opt_out_via_env()`, `test_rate_limit_backup_logic_with_dis...`

---

### C231: `8. Лимиты и стоимость` (4 nodes)

**Файл:** `app.py`
**Hub:** `parse_llm_json_safe()`

Функция/утилита: parse_llm_json_safe()

**Содержит:** `parse_llm_json_safe()`, `Safe wrapper: возвращает {} при любой...`, `test_parse_llm_json_invalid_returns_e...`, `parse_llm_json_safe: невалидный JSON ...`

---

### C34: `RoleStateMiddleware` (4 nodes)

**Файл:** `app.py`
**Hub:** `RoleStateMiddleware`

Middleware ролей

Cookie-based role switching.

**Содержит:** `RoleStateMiddleware`, `BaseHTTPMiddleware`, `.dispatch()`, `Добавляет request.state.current_role ...`

---

### C32: `hash_password` (4 nodes)

**Файл:** `app.py`
**Hub:** `hash_password()`

Хеширование пароля

verify_password().

**Содержит:** `hash_password()`, `bcrypt хеш пароля. Если bcrypt недост...`, `test_hash_password_and_verify()`, `bcrypt/sha256 round-trip`

---

### C35: `few_shot.py` (4 nodes)

**Файл:** `few_shot.py`
**Hub:** `few_shot.py`

Примеры для LLM

FEW_SHOT_4C85941A = упор продольный (ЛМША.301314.010).

**Содержит:** `few_shot.py`, `get_relevant_few_shot()`, `Few-shot примеры: 3 примера для разны...`, `F16.3: выбирает few-shot по типу дета...`

---

### C36: `workshops_tehinkom.py` (4 nodes)

**Файл:** `workshops_tehinkom.py`
**Hub:** `workshops_tehinkom.py`

Реальные цеха (M28)

5 цехов × 36 операций = 2190 символов. Подключается в $workshops_context.

**Содержит:** `workshops_tehinkom.py`, `format_workshops_for_prompt()`, `Реальные данные Техинкома — workshops...`, `Возвращает текстовый блок для system ...`

---

### C37: `JsonFormatter` (3 nodes)

**Файл:** `app.py`
**Hub:** `JsonFormatter`

JSON logging

app.py:JsonFormatter — структурированный JSON-логгер.

**Содержит:** `JsonFormatter`, `.format()`, `V6-22: JSON-формат логов для producti...`

---

## 2. Документация (community docs/)

**Всего:** 74 community

- **C16** (42 nodes) `docs/17-deployment.md` — Deployment Guide — развёртывание БИТ.Технолог
- **C17** (40 nodes) `docs/05-techinkom-context.md` — БИТ.Технолог — Данные от Техинкома (16.07.2026)
- **C18** (40 nodes) `docs/14-roles-user-guide.md` — Руководство пользователя по 4 ролям
- **C22** (40 nodes) `docs/16-database-schema.md` — Схема базы данных
- **C24** (35 nodes) `docs/01-product-design.md` — БИТ.Технолог — Product Design v0.4
- **C25** (30 nodes) `docs/08-competitors-ui-analysis.md` — 08-competitors-ui-analysis.md
- **C28** (29 nodes) `docs/03-training-architecture.md` — БИТ.Технолог — Архитектура обучения
- **C29** (27 nodes) `README.md` — БИТ.Технолог — прототип
- **C30** (25 nodes) `docs/19-security-compliance.md` — Безопасность и соответствие 152-ФЗ
- **C38** (24 nodes) `docs/09-open-questions.md` — Открытые вопросы по продукту
- **C39** (21 nodes) `README.md` — README.md
- **C40** (20 nodes) `docs/02-architecture.md` — БИТ.Технолог — Архитектура MVP v0.4.9 (actual state)
- **C41** (19 nodes) `docs/07-audit-log.md` — Аудит БИТ.Технолог — история проверок
- **C184** (15 nodes) `USER_GUIDE.md` — USER_GUIDE.md
- **C42** (15 nodes) `docs/08-competitors.md` — Вопросы представителю ИИ-Технолога (tab-is.ru)
- **C43** (15 nodes) `docs/11-tehnolog-guide.md` — 11-tehnolog-guide.md
- **C44** (15 nodes) `docs/13-developer-guide.md` — Гайд для разработчика — БИТ.Технолог
- **C185** (14 nodes) `docs/06-ux-flow.md` — БИТ.Технолог — UX-флоу технолога
- **C186** (13 nodes) `docs/10-product-fit-and-roadmap.md` — Roadmap после gap-анализа — что НЕ учтено и план закрытия
- **C187** (13 nodes) `docs/README.md` — БИТ.Технолог — Проектная документация
- **C188** (11 nodes) `docs/20-faq.md` — История версий
- **C189** (11 nodes) `docs/20-project-guide.md` — 20-project-guide.md
- **C190** (10 nodes) `docs/04-pilot-roadmap.md` — БИТ.Технолог — Roadmap от демо к пилоту
- **C191** (10 nodes) `docs/15-api-reference.md` — Админ-панель
- **C192** (9 nodes) `docs/20-faq.md` — Для админа
- **C195** (8 nodes) `.github/ISSUE_TEMPLATE/bug_report.md` — bug_report.md
- **C193** (8 nodes) `docs/18-troubleshooting.md` — Универсальная диагностика
- **C194** (8 nodes) `docs/20-faq.md` — Для технолога
- **C203** (7 nodes) `.github/ISSUE_TEMPLATE/feature_request.md` — feature_request.md
- **C196** (7 nodes) `docs/12-admin-guide.md` — 9. Часто задаваемые вопросы
- **C197** (7 nodes) `docs/15-api-reference.md` — UI Pages (HTML)
- **C198** (7 nodes) `docs/20-faq.md` — Для разработчика
- **C199** (7 nodes) `docs/adr/0002-on-prem-yandexgpt.md` — 0002-on-prem-yandexgpt.md
- **C200** (7 nodes) `docs/adr/0003-rag-tfidf-not-vector-db.md` — 0003-rag-tfidf-not-vector-db.md
- **C201** (7 nodes) `docs/adr/0004-monolith-not-microservices.md` — 0004-monolith-not-microservices.md
- **C202** (7 nodes) `docs/adr/0007-parse-llm-json-defensive.md` — 0007-parse-llm-json-defensive.md
- **C204** (6 nodes) `docs/12-admin-guide.md` — 0. ⚠️ Критично: 152-ФЗ (Российский GDPR)
- **C205** (6 nodes) `docs/12-admin-guide.md` — 4. Что делать если сломалось
- **C207** (6 nodes) `docs/15-api-reference.md` — Импорт / Экспорт
- **C206** (6 nodes) `docs/15-api-reference.md` — Система
- **C209** (6 nodes) `docs/18-troubleshooting.md` — Проблемы с генерацией AI
- **C208** (6 nodes) `docs/18-troubleshooting.md` — Проблемы с UI
- **C210** (6 nodes) `docs/20-faq.md` — FAQ — Часто задаваемые вопросы
- **C212** (6 nodes) `docs/20-faq.md` — Общие вопросы
- **C211** (6 nodes) `docs/20-faq.md` — О системе
- **C213** (6 nodes) `docs/adr/0001-use-sqlite-not-postgres.md` — 0001-use-sqlite-not-postgres.md
- **C214** (6 nodes) `docs/adr/0002-on-prem-yandexgpt.md` — ADR-0002: YandexGPT (on-premise через cloud) для генерации ТК
- **C215** (6 nodes) `docs/adr/0005-specialized-prompts.md` — 0005-specialized-prompts.md
- **C216** (6 nodes) `docs/adr/0006-real-workshops-in-prompts.md` — 0006-real-workshops-in-prompts.md
- **C217** (6 nodes) `docs/adr/0008-csrf-required.md` — 0008-csrf-required.md
- **C218** (6 nodes) `docs/adr/0009-graphify-knowledge-graph.md` — 0009-graphify-knowledge-graph.md
- **C219** (5 nodes) `docs/12-admin-guide.md` — Гайд для администратора — БИТ.Технолог
- **C220** (5 nodes) `docs/12-admin-guide.md` — 1. Доступы
- **C221** (5 nodes) `docs/12-admin-guide.md` — 5. Бэкапы
- **C222** (5 nodes) `docs/15-api-reference.md` — API Reference — полный справочник
- **C225** (5 nodes) `docs/15-api-reference.md` — Генерация (AI)
- **C227** (5 nodes) `docs/15-api-reference.md` — Редактирование операций
- **C226** (5 nodes) `docs/15-api-reference.md` — Утверждение / Открытие
- **C224** (5 nodes) `docs/15-api-reference.md` — Справочники
- **C223** (5 nodes) `docs/15-api-reference.md` — Отчёты пилота
- **C230** (5 nodes) `docs/18-troubleshooting.md` — Проблемы с входом / ролями
- **C228** (5 nodes) `docs/18-troubleshooting.md` — Проблемы с импортом/экспортом
- **C229** (5 nodes) `docs/18-troubleshooting.md` — Проблемы с деплоем
- **C232** (4 nodes) `docs/12-admin-guide.md` — 0.1 ⚠️ Sandbox wipe
- **C233** (4 nodes) `docs/12-admin-guide.md` — 2. Роли и пользователи
- **C234** (4 nodes) `docs/12-admin-guide.md` — 6. Обновление (deploy)
- **C235** (4 nodes) `docs/12-admin-guide.md` — 7. Мониторинг
- **C236** (4 nodes) `docs/12-admin-guide.md` — 8. Лимиты и стоимость
- **C237** (4 nodes) `docs/15-api-reference.md` — Детали (CRUD)
- **C238** (4 nodes) `docs/15-api-reference.md` — Примеры типичных сценариев
- **C242** (4 nodes) `docs/18-troubleshooting.md` — Troubleshooting — типичные проблемы и решения
- **C239** (4 nodes) `docs/18-troubleshooting.md` — Проблемы с производительностью
- **C241** (4 nodes) `docs/18-troubleshooting.md` — Проблемы с БД
- **C240** (4 nodes) `docs/18-troubleshooting.md` — Проблемы с безопасностью

---

## 3. Тесты

**Все community:** 1 (C1, 104 nodes — все тесты в test_app.py)

Graphify не выделяет тесты в подграфы. 290 pytest функций в одном модуле.

---

## 4. HTML templates

**Всего:** 0 community


---

## 5. Static (CSS, JS)

**Всего:** 1 community

- **C0** (105 nodes) `static/htmx.min.js` — htmx.min.js

---


## Итог: что LLM может извлечь из этого файла

**Без чтения кода:**
- Все 22 модуля с описанием (что делает, какие endpoints, зачем)
- Все 9 ADR — почему именно так, а не иначе
- 265 community — что есть в проекте
- 35+ endpoint'ов — какие есть
- 19 таблиц БД — структура данных (через docs/16-database-schema.md)

**С чтением кода (только при необходимости):**
- app.py (5000 строк) — детали конкретных endpoint'ов
- db.py — SQL схема
- prompts.py — текст промтов

**Что НЕ покрыто этим файлом:**
- Содержимое HTML templates (UI в деталях)
- Содержимое CSS (стили)
- 290 тестов

---

## Рекомендуемый промт для LLM

```
Ты — внешний технический ревьюер.

Перед тобой:
1. SEMANTIC_NOTES.md (этот файл) — обогащение knowledge graph проекта БИТ.Технолог
2. docs/adr/*.md — 9 ключевых архитектурных решений

Дай анализ по разделам:
1. Сильные стороны (что сделано хорошо)
2. Узкие места (где скорее всего сломается)
3. Риски для пилота 27 июля (5 дней до запуска)
4. Что обязательно исправить ДО пилота (5-7 пунктов)
5. Что отложить на после пилота

Цитируй конкретные community (C{n}) и ADR номера.
```

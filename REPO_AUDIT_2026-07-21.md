# АУДИТ РЕПО — 2026-07-21 (после Sprint 9)

**Дата:** 2026-07-21  
**Версия:** v0.8.5 (после Sprint 9: метрики + inline-edit + полировка UI)  
**Метод:** прочитал каждый файл, классифицировал

---

## 1. CORE v0.8 (используется, актуально) ✅

| Файл | Размер | Что делает |
|------|--------|------------|
| `app.py` | 41K / 1028 строк | Главный FastAPI: 28 routes, 4 Jinja filter (from_json, ru_level, ru_sourcing) |
| `domain/llm_provider.py` | — | LLMProvider + MockLLM + YandexGPT + GigaChat |
| `gateways/one_c_gateway.py` | — | OneCGateway + FileGateway + HttpGateway (заглушка) |
| `repositories/db.py` | 42K | Singleton SQLite, generic CRUD, миграция через SQL |
| `migrations/001_v0_8_init.sql` | — | 33 таблицы |
| `services/auth.py` | 8K | 5 ролей, Basic Auth, cookie sessions, has_permission |
| `services/rs_factory.py` | 16K | Детерминированный алгоритм, 8 осей, is_deterministic |
| `services/rag.py` | 15K | TF-IDF + RAG v2 (material_id FK, mass_kg бонус) |
| `services/evidence.py` | 12K | Светофор 🟢🟡🔴⚪, топ-3 аналога, OperationEvidence |
| `services/notices.py` | 11K | Извещения end-to-end, ГОСТ 2.503 |
| `services/tp_parser.py` | 13K | OCR → структурированный ТП |
| `services/one_c_loader.py` | 10K | Загрузчик НСИ из XML в БД |
| `services/generate_one_c_mock.py` | 26K | Генератор реалистичной эмуляции 1С:ERP (6 XML, 113 записей) |
| `services/metrics.py` | 4K | Метрики пилота b (время) + c (% зелёных) — Sprint 9 |
| `seeds/seed_etalons.py` | — | 2 PDF Техинкома → эталоны |
| `seeds/seed_items.py` | — | 14 items + 12 составных |
| `seeds/seed_more_etalons.py` | — | 5 синтетических эталонов |
| `seeds/seed_tech_cards.py` | — | ТК из эталонов |
| `seeds/seed_test_ai_tc.py` | — | Тестовая ТК с AI-нормами (Кронштейн боковой) |
| `seeds/seed_test_notice.py` | — | Тестовое извещение И-2026-014 |
| `templates/dashboard.html` | — | Главная, 5 counters + задачи + извещения |
| `templates/products.html` | — | Список + поиск + фильтр по level |
| `templates/detail.html` | — | 5 табов + светофор + inline-edit |
| `templates/notice_form.html` | — | Форма создания извещения |
| `templates/notice_detail.html` | — | AI diff + решение |
| `templates/notices.html` | — | Список извещений |
| `templates/knowledge.html` | — | Эталоны + пометка синтетических |
| `templates/profiles.html` | — | 8 осей профиля РС |
| `templates/llm_admin.html` | — | Провайдеры LLM + назначения |
| `templates/login.html` | — | Login-форма |
| `templates/settings.html` | — | Настройки (admin) |
| `templates/metrics.html` | — | Страница метрик — Sprint 9 |
| `templates/help.html` | — | Помощь |
| `templates/base.html` | — | Базовый с inline стилями v0.8 |
| `templates/item_generate.html` | — | Форма генерации ТК |
| `test/test_v0_8.py` | — | 78 unit-тестов |
| `test/test_e2e.py` | — | 13 e2e-тестов |
| `check_all_buttons.py` | — | Playwright-чекер (16 сценариев) |

**ИТОГО core: ~250 KB кода, 91/91 тестов**

---

## 2. МЁРТВЫЙ КОД (от M22-M33, до "полной переделки" M34) ❌

21 файл, 312 КБ — НЕ используется в новой структуре.

| Файл | Размер | Почему мёртвый |
|------|--------|----------------|
| `rag.py` | 17K | Sprint 2 TF-IDF, заменён `services/rag.py` |
| `importers.py` | 18K | Старый импорт, заменён `services/one_c_loader.py` |
| `prompts.py` | 30K | Спринт 1, не используется в v0.8 |
| `few_shot.py` | 16K | Sprint 3, не используется |
| `mock_data.py` | 6K | Sprint 1, заменён `services/generate_one_c_mock.py` |
| `mock_llm.py` | 14K | Sprint 1, заменён `domain/llm_provider.py` |
| `pilot_report.py` | 13K | Sprint 4, нет endpoint в app.py |
| `techinkom_seed.py` | 21K | Sprint 2, заменён `seeds/seed_items.py` |
| `workshops_tehinkom.py` | 5K | Sprint 2, не используется |
| `drawing_recognize.py` | 9K | Sprint 2 OCR, заменён `services/tp_parser.py` |
| `e2e_technologist.py` | 27K | Sprint 4, заменён `test/test_e2e.py` |
| `test_app.py` | 132K | Sprint 1-4, заменён `test/test_v0_8.py` + `test/test_e2e.py` |
| `metrics_auto.py` | 6K | Sprint 4, не используется |
| `check_all_roles.py` | 7K | Старый ручной чекер |
| `check_buttons.py` | 6K | Старый чекер, заменён `check_all_buttons.py` |
| `structure.json` | 1K | Sprint 4, не используется |
| `equipment.json` | 3K | Данные переехали в БД (workshops/professions/equipment) |
| `init-git.bat` | 2K | Windows-скрипт, не нужен (используем git напрямую) |
| `start.bat` | 1K | Windows-скрипт |
| `update.bat` | 1K | Windows-скрипт |
| `graphify-out/` | — | AST-отчёт, regenerable |

---

## 3. ШАБЛОНЫ НЕИСПОЛЬЗУЕМЫЕ ❌

32 из 47 шаблонов НЕ рендерятся в app.py. Большинство от M22-M26 (до полной переделки).

| Категория | Шаблоны | Почему |
|-----------|---------|--------|
| admin/* (10 шт) | admin.html, admin_backup.html, admin_errors.html, admin_llm_calls.html, admin_login_log.html, admin_rag.html, admin_settings.html, admin_system.html, admin_users.html | admin.py вынесен в M34, нет endpoint'ов |
| partials (6 шт) | _alternatives.html, _ocr_result.html, _rag_similar.html, _related.html, _resource_specs.html | M22-M26, не используются (grep `{% include %}` находит только base.html + _index_table.html) |
| pilot/* (3 шт) | pilot.html, pilot_learning.html, pilot_report.html | Sprint 4 |
| Прочие | 404.html, audit.html, demo.html, detail_form.html, diff.html, equipment_list.html, hierarchy.html, index.html, iot_list.html, learning.html, llm_debug.html, materials_list.html, print.html | Устаревшие (до M34) или никогда не были |

---

## 4. STATIC НЕИСПОЛЬЗУЕМЫЙ ⚠️

| Файл | Размер | Почему |
|------|--------|--------|
| `static/htmx.min.js` | 47K | НЕ подключён в base.html, нигде нет hx-* запросов |
| `static/qrcode.min.js` | 20K | Подключён в `templates/print.html`, но `print.html` НЕ рендерится |
| `static/style.css` | 16K | НЕ подключён — base.html inline стили v0.8 (--v8-brand) |
| `static/design-system.css` | 34K | НЕ подключён — base.html inline стили v0.8 (--c-brand) |

**ВЫВОД: 117 KB мёртвого JS/CSS в static/**

---

## 5. ДОКУМЕНТАЦИЯ

### Актуальная ✅
- `README.md` — НО говорит "v0.4.9" (нужно обновить до v0.8.5)
- `CHANGELOG.md` — есть запись про M34, актуален
- `MISTAKES.md` — 31 урок M1-M31, ценный, актуальный
- `LICENSE` — оставить
- `.gitignore`, `.editorconfig`, `.flake8` — оставить
- `docs/adr/0001-0011.md` — 11 ADR, все актуальны
- `docs/21-v0.8-design.md` — дизайн v0.8

### Требуют обновления ⚠️
- `README.md` — версия, тесты, экраны (v0.4.9 → v0.8.5, 219 → 91, 8 → 9 экранов)
- `docs/01-08.md` — почти все говорят "v0.4.x" (кроме 21-v0.8-design.md)
- `docs/10-20.md` — частично устарели
- `docs/16-database-schema.md` — может быть устарел (33 таблицы)
- `docs/15-api-reference.md` — может быть устарел
- `docs/18-troubleshooting.md` — частично

### Legacy (контекст, не runtime) 📦
- `docs/legacy-context/*.md` (25 файлов) — старые разборы Сергея, полезны как контекст
- `AUDIT_v1.md ... AUDIT_v8.md` (8 файлов) — мои старые аудиты (до M34)
- `AUDIT_2026-07-20.md` — 10KB, более новый аудит
- `E2E_REPORT.md` — старый отчёт
- `USER_GUIDE.md` — может быть устарел

### Deploy (актуально) ✅
- `deploy/*.sh` (10 скриптов) — деплой на Beget
- `deploy/README_DEPLOY.md` — инструкция
- `requirements.txt` — НО не обновлён с M34 (всё ещё scipy/numpy/scikit-learn от v0.4)

---

## 6. ATTACHMENTS (клиентские) ✅

222 файла, 32M:
- 14 PDF (эталоны, чертежи)
- 4 XLSX
- 2 DOCX  
- 93 PNG
- 1 JPG
- 94 TXT
- 4 MD
- 3 JSON
- + `ocr/`, `ocr_output/`, `extracted/`, `workshop_context.md` и др.

**Стоит оставить — клиент дал всё это в рамках сессии**

---

## 7. MIGRATIONS

- `migrations/001_v0_8_init.sql` — 33 таблицы, актуальна
- `migrations/` — других нет (M34 создал одну)

---

## 8. STAT (только для чтения)

- `graphify-out/GRAPH_REPORT.md`, `SEMANTIC_NOTES.md`, `graph.html`, `graph.json`, `manifest.json` — AST-отчёт, regenerable (M29)
- `screen_dashboard.png`, `screen_detail.png`, `screen_products.png` — мои скриншоты
- `screen_v2_*.png` — Sprint 9 скриншоты

---

## 9. .github/ (issue templates)

- `bug_report.md`, `feature_request.md` — стандартные шаблоны, оставить

---

## ИТОГО: что можно удалить без потерь

| Категория | Что | Размер |
|-----------|-----|--------|
| Мёртвый код | 15 .py файлов в корне | ~190 KB |
| Мёртвые шаблоны | 32 .html в templates/ | ~80 KB |
| Мёртвый static | htmx.min.js + qrcode.min.js + 2 css | 117 KB |
| Legacy доки | 8 AUDIT_v*.md | ~50 KB |
| **ВСЕГО** | | **~440 KB** |

---

## ЧТО Я ПОНИМАЮ ✅

- Архитектуру v0.8 (domain/gateways/services/repositories)
- 28 routes, 4 Jinja filter, 91 теста
- 5 ролей, permissions, has_permission
- 8 осей профиля РС, is_deterministic
- RAG v2 с material_id FK, mass_kg бонус
- Светофор: 🟢 factory_data / 🟡 analog_estimate / 🔴 ai_guess / ⚪ нет данных
- Извещения end-to-end (создание → автопоиск → AI diff → пересчёт)
- Метрики b + c, pilot_runs/pilot_metrics
- Inline-edit через showConfirmInput
- Деплой на Beget (deploy/*.sh)

## ЧТО НЕ ПОНИМАЮ ❓ (нужны ответы Сергея)

1. **README.md** — обновлять до v0.8.5 или оставить v0.4.9 (он говорит пилоте 27.07)?
2. **docs/01-20.md** — обновлять или оставить как историю?
3. **Мёртвый код в корне** — удалить 15 .py файлов или оставить для истории?
4. **32 мёртвых шаблона** — удалить или оставить?
5. **static/htmx.min.js** — нужен ли HTMX? Или оставить на будущее?
6. **static/style.css + design-system.css** — объединить в один или удалить старый?
7. **requirements.txt** — обновлять (убрать sklearn/numpy) или оставить?
8. **graphify-out/** — оставить (regenerable) или удалить (5 файлов)?
9. **deploy/ на Windows .bat** — есть, но я на Linux, оставить?
10. **Клиентские файлы в attachments/ (32M)** — все 222 нужны в репо? Или только эталонные PDF?

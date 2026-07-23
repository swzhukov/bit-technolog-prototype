# КАРТА СИСТЕМЫ БИТ.Технолог v7

**Дата:** 2026-07-23  
**HEAD:** 71a8374 (после Sprint 6 = 16/16 done)

## 1. Endpoints (42)

| # | Метод | Путь | Функция | Тип |
|---|-------|------|---------|-----|
| 1 | GET | `/login` | `login_page` | HTMLResponse |
| 2 | POST | `/login` | `login_post` | JSON |
| 3 | GET | `/logout` | `logout` | JSON |
| 4 | GET | `/settings` | `settings_page` | HTMLResponse |
| 5 | POST | `/settings/llm` | `settings_save_llm` | JSON |
| 6 | GET | `/` | `dashboard` | HTMLResponse |
| 7 | GET | `/products` | `products` | HTMLResponse |
| 8 | GET | `/detail/{item_id}` | `detail` | HTMLResponse |
| 9 | GET | `/details/new` | `details_new_form` | HTMLResponse |
| 10 | POST | `/details/new` | `details_new_create` | JSON |
| 11 | GET | `/items/{item_id}/generate` | `item_generate_form` | HTMLResponse |
| 12 | POST | `/items/{item_id}/generate` | `item_generate_post` | JSON |
| 13 | POST | `/api/items/{item_id}/export-to-1c` | `api_export_to_1c` | JSON |
| 14 | GET | `/notices` | `notices` | HTMLResponse |
| 15 | GET | `/notices/new` | `notice_new` | HTMLResponse |
| 16 | POST | `/notices/new` | `notice_create` | JSON |
| 17 | GET | `/notices/{notice_id}` | `notice_detail` | HTMLResponse |
| 18 | POST | `/notices/{notice_id}/generate-diff` | `notice_generate_diff` | JSON |
| 19 | POST | `/notices/{notice_id}/resolve` | `notice_resolve` | JSON |
| 20 | GET | `/api/change-notices` | `api_list_notices` | JSON |
| 21 | GET | `/api/change-notices/{notice_id}` | `api_notice` | JSON |
| 22 | POST | `/api/change-notices/{notice_id}/diff` | `api_notice_diff` | JSON |
| 23 | GET | `/profiles` | `profiles` | HTMLResponse |
| 24 | GET | `/knowledge` | `knowledge` | HTMLResponse |
| 25 | GET | `/llm-admin` | `llm_admin` | HTMLResponse |
| 26 | GET | `/help` | `help_page` | HTMLResponse |
| 27 | GET | `/metrics` | `metrics_page` | HTMLResponse |
| 28 | POST | `/metrics/record-green` | `metrics_record_green` | JSON |
| 29 | GET | `/audit` | `audit_page` | HTMLResponse |
| 30 | GET | `/rs` | `rs_export_page` | HTMLResponse |
| 31 | GET | `/api/rs/list` | `api_rs_list` | JSON |
| 32 | GET | `/api/rs/download/{filename}` | `api_rs_download` | JSON |
| 33 | GET | `/health` | `health` | JSON |
| 34 | GET | `/api/items` | `api_items` | JSON |
| 35 | GET | `/api/tech-cards/{tech_card_id}/rs-preview` | `api_rs_preview` | JSON |
| 36 | GET | `/api/tech-cards/{tech_card_id}/evidence` | `api_evidence` | JSON |
| 37 | POST | `/api/operations/{operation_id}/confirm` | `api_confirm_operation` | JSON |
| 38 | POST | `/api/operations/{operation_id}/update` | `api_update_operation` | JSON |
| 39 | POST | `/api/tech-cards/{tech_card_id}/regenerate` | `api_regenerate` | JSON |
| 40 | GET | `/api/tech-cards/{tech_card_id}/diff` | `api_tech_card_diff` | JSON |
| 41 | POST | `/api/tech-cards/{tech_card_id}/approve` | `api_approve` | JSON |
| 42 | POST | `/api/change-notices/{notice_id}/process` | `api_process_notice` | JSON |

## 2. Templates (19)

| # | Файл | Назначение |
|---|------|------------|
| 1 | `_index_table.html` | |
| 2 | `audit.html` | |
| 3 | `base.html` | |
| 4 | `dashboard.html` | |
| 5 | `detail.html` | |
| 6 | `detail_new.html` | |
| 7 | `help.html` | |
| 8 | `item_generate.html` | |
| 9 | `knowledge.html` | |
| 10 | `llm_admin.html` | |
| 11 | `login.html` | |
| 12 | `metrics.html` | |
| 13 | `notice_detail.html` | |
| 14 | `notice_form.html` | |
| 15 | `notices.html` | |
| 16 | `products.html` | |
| 17 | `profiles.html` | |
| 18 | `rs_export.html` | |
| 19 | `settings.html` | |

## 3. Tables (33)

| # | Таблица |
|---|---------|
| 1 | `chassis` |
| 2 | `professions` |
| 3 | `workshops` |
| 4 | `equipment` |
| 5 | `materials` |
| 6 | `rs_output_profiles` |
| 7 | `llm_providers` |
| 8 | `product_models` |
| 9 | `product_configurations` |
| 10 | `items` |
| 11 | `bom_links` |
| 12 | `tech_cards` |
| 13 | `operations` |
| 14 | `operation_materials` |
| 15 | `resource_specs` |
| 16 | `change_notices` |
| 17 | `ext_attributes` |
| 18 | `work_history` |
| 19 | `etalons` |
| 20 | `tech_rules` |
| 21 | `edits` |
| 22 | `llm_model_assignments` |
| 23 | `llm_calls` |
| 24 | `pilot_users` |
| 25 | `audit_logins` |
| 26 | `app_settings` |
| 27 | `pilot_metrics` |
| 28 | `drafts` |
| 29 | `draft_versions` |
| 30 | `history` |
| 31 | `kompas_events` |
| 32 | `iot` |
| 33 | `benchmarks` |

## 4. FK: 29

## 5. 4 роли × permissions (services/auth.py)

| Роль | Permissions | Display |
|------|-------------|---------|
| admin (techadmin, llmadmin) | view_all, edit_all, manage_rs_profiles, manage_llm_providers, manage_llm_model_assignments, manage_changelog, view_audit_logins, view_llm_calls | Администратор |
| main_technologist (vorobyev, baranov) | view/edit/approve_tech_cards, manage_tech_rules, view_work_history, view_change_notices, **view_audit_logins, view_llm_calls** (B4) | Главный технолог |
| technologist (tarrietsky) | view/edit/approve_own_tech_cards, view_resource_specs, view_etalons, view_work_history | Технолог |
| workshop_chief (golubev) | view_tech_cards, approve_tech_cards, view_resource_specs, view_change_notices, view_etalons | Начальник цеха |

## 6. UI nav (12 ссылок в base.html)

1. Мои задачи (`/`)
2. Изделия (`/products`)
3. База знаний (`/knowledge`)
4. Извещения (`/notices`)
5. Выгрузка РС (`/rs`)
6. **Шаблоны маршрутов** (`/profiles`) — admin + main
7. **Метрики** (`/metrics`) — admin + main
8. **Аудит** (`/audit`) — admin + main [B4 new]
9. **Модели LLM** (`/llm-admin`) — admin + main
10. **Настройки** (`/settings`) — admin only
11. Помощь (`/help`)
12. Выход (`/logout`)

## 7. Структура проекта (v0.8 + Sprint 6)

```
bit-technolog-prototype/
├── app.py (1700+ строк, 42 endpoints)
├── services/
│   ├── audit.py     — log_history() (B3)
│   ├── auth.py      — ROLES + _ROLE_ALIASES
│   ├── state.py     — sessions + rate_limit (D1)
│   ├── notices.py
│   ├── rag.py
│   ├── rs_factory.py
│   ├── one_c_loader.py
│   ├── tp_parser.py
│   ├── evidence.py
│   ├── metrics.py
│   └── text_utils.py
├── domain/
│   ├── llm_provider.py — YandexGPT + OpenAI + Mock (D7 fallback)
│   └── prompts.py — REFINE_PROMPT + workshops_context
├── repositories/
│   └── db.py — sqlite3 WAL + transaction()
├── gateways/
│   └── one_c_gateway.py
├── templates/ (19 файлов)
├── migrations/ (003_shared_state.sql)
├── seed/ — workshop_context.md
├── static/
├── certs/ — TLS self-signed
├── audit/ (тесты, FINDINGS, MASTER_PROMPT, PENALTIES)
├── wiki/tehinkom/ (8 файлов + OCR)
└── MISTAKES.md (1753 строк)
```

## 8. Что нового в v7 (после Sprint 6)

- **B4 (audit UI)**: `/audit` 3 таба (logins 4517, history 357, llm 237)
- **C3 (diff ТК)**: `/api/tech-cards/<built-in function id>/diff` + модалка в detail.html
- **D1 (shared state)**: SQLite sessions + rate_limit_buckets
- **D7 (YandexGPT fallback)**: 1bitai → YandexGPT → Mock
- **E1 (workshop_context)**: справочник операций Техинкома в LLM prompt
- **E2 (equipment Техинкома)**: 27 единиц в БД (всего 57)
- **E3-E5 (wiki + OCR + graphify)**: 8 .md + 2 OCR + 3864 nodes

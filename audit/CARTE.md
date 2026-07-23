# КАРТА СИСТЕМЫ БИТ.Технолог v1.0.0

## Дата: 2026-07-22

## 1. Endpoints (38)

| Метод | Путь | Функция |
|-------|------|---------|
| GET | `/login` | `login_page` |
| POST | `/login` | `login_post` |
| GET | `/logout` | `logout` |
| GET | `/settings` | `settings_page` |
| POST | `/settings/llm` | `settings_save_llm` |
| GET | `/` | `dashboard` |
| GET | `/products` | `products` |
| GET | `/detail/{item_id}` | `detail` |
| GET | `/details/new` | `detail_new_placeholder` |
| GET | `/items/{item_id}/generate` | `item_generate_form` |
| POST | `/items/{item_id}/generate` | `item_generate_post` |
| POST | `/api/items/{item_id}/export-to-1c` | `api_export_to_1c` |
| GET | `/notices` | `notices` |
| GET | `/notices/new` | `notice_new` |
| POST | `/notices/new` | `notice_create` |
| GET | `/notices/{notice_id}` | `notice_detail` |
| POST | `/notices/{notice_id}/generate-diff` | `notice_generate_diff` |
| POST | `/notices/{notice_id}/resolve` | `notice_resolve` |
| GET | `/api/change-notices` | `api_list_notices` |
| GET | `/api/change-notices/{notice_id}` | `api_notice` |
| GET | `/profiles` | `profiles` |
| GET | `/knowledge` | `knowledge` |
| GET | `/llm-admin` | `llm_admin` |
| GET | `/help` | `help_page` |
| GET | `/metrics` | `metrics_page` |
| POST | `/metrics/record-green` | `metrics_record_green` |
| GET | `/rs` | `rs_export_page` |
| GET | `/api/rs/list` | `api_rs_list` |
| GET | `/api/rs/download/{filename}` | `api_rs_download` |
| GET | `/health` | `health` |
| GET | `/api/items` | `api_items` |
| GET | `/api/tech-cards/{tech_card_id}/rs-preview` | `api_rs_preview` |
| GET | `/api/tech-cards/{tech_card_id}/evidence` | `api_evidence` |
| POST | `/api/operations/{operation_id}/confirm` | `api_confirm_operation` |
| POST | `/api/operations/{operation_id}/update` | `api_update_operation` |
| POST | `/api/tech-cards/{tech_card_id}/regenerate` | `api_regenerate` |
| POST | `/api/tech-cards/{tech_card_id}/approve` | `api_approve` |
| POST | `/api/change-notices/{notice_id}/process` | `api_process_notice` |

## 2. Templates (18)
- `_index_table.html`
- `base.html`
- `dashboard.html`
- `detail.html`
- `detail_new_placeholder.html`
- `help.html`
- `item_generate.html`
- `knowledge.html`
- `llm_admin.html`
- `login.html`
- `metrics.html`
- `notice_detail.html`
- `notice_form.html`
- `notices.html`
- `products.html`
- `profiles.html`
- `rs_export.html`
- `settings.html`

## 3. Роли (4)

| Роль | Display | Permissions |
|------|---------|-------------|
| `technologist` | Технолог | view_tech_cards, edit_own_tech_cards, approve_own_tech_cards, view_resource_specs, view_etalons, view_work_history |
| `main_technologist` | Главный технолог | view_tech_cards, edit_tech_cards, approve_tech_cards, approve_etalons, manage_tech_rules, view_resource_specs, edit_resource_specs, view_etalons, view_work_history, view_change_notices |
| `workshop_chief` | Начальник цеха | view_tech_cards, approve_tech_cards, view_resource_specs, view_change_notices, view_etalons |
| `admin` | Администратор | view_all, edit_all, manage_rs_profiles, manage_llm_providers, manage_llm_model_assignments, view_llm_calls, view_change_notices, view_etalons |

## 4. Foreign Keys (31)

| From | To |
|------|-----|
| `workshops.parent_id` | `workshops.id` |
| `equipment.workshop_id` | `workshops.id` |
| `product_models.default_rs_profile_id` | `rs_output_profiles.id` |
| `product_models.chassis_id` | `chassis.id` |
| `product_configurations.product_model_id` | `product_models.id` |
| `items.material_id` | `materials.id` |
| `items.configuration_id` | `product_configurations.id` |
| `items.product_model_id` | `product_models.id` |
| `items.parent_item_id` | `items.id` |
| `bom_links.configuration_id` | `product_configurations.id` |
| `bom_links.child_item_id` | `items.id` |
| `bom_links.parent_item_id` | `items.id` |
| `tech_cards.llm_provider_id` | `llm_providers.id` |
| `tech_cards.item_id` | `items.id` |
| `operations.profession_id` | `professions.id` |
| `operations.equipment_id` | `equipment.id` |
| `operations.workshop_id` | `workshops.id` |
| `operations.tech_card_id` | `tech_cards.id` |
| `operation_materials.material_id` | `materials.id` |
| `operation_materials.operation_id` | `operations.id` |
| `resource_specs.rs_profile_id` | `rs_output_profiles.id` |
| `resource_specs.tech_card_id` | `tech_cards.id` |
| `resource_specs.item_id` | `items.id` |
| `edits.operation_id` | `operations.id` |
| `edits.tech_card_id` | `tech_cards.id` |
| `llm_model_assignments.llm_provider_id` | `llm_providers.id` |
| `llm_calls.llm_provider_id` | `llm_providers.id` |
| `drafts.item_id` | `items.id` |
| `draft_versions.draft_id` | `drafts.id` |
| `pilot_runs.tc_id` | `tech_cards.id` |
| `pilot_runs.item_id` | `items.id` |

## 5. UI Elements по template

### `_index_table.html` (4 элементов)
- link: `{{ d.designation }} -> /detail/{{ d.id }}`
- link: `{{ d.name or '—' }} -> /detail/{{ d.id }}`
- link: `Открыть -> /detail/{{ d.id }}`
- link: `＋ Новая деталь -> /details/new`

### `base.html` (12 элементов)
- link: `Войти -> ?login=1`
- link: `Мои задачи -> /`
- link: `Изделия -> /products`
- link: `База знаний -> /knowledge`
- link: `Выгрузка РС -> /rs`
- link: `Шаблоны маршрутов -> /profiles`
- link: `Метрики -> /metrics`
- link: `Модели LLM -> /llm-admin`
- link: `Настройки -> /settings`
- link: `Помощь -> /help`
- link: `Выход -> /logout`
- link: `Войти -> /login`

### `dashboard.html` (6 элементов)
- link: `Открыть список изделий -> /products`
- link: `{{ top_draft.designation }} -> /detail/{{ top_draft.item_id }}`
- link: `Открыть -> /detail/{{ t.item_id }}`
- link: `Изделия -> /products`
- link: `Разобрать -> /notices/{{ n.id }}`
- link: `Изделиях -> /products`

### `detail.html` (16 элементов)
- button: `Утвердить и в эталоны`
- button: `Перегенерировать`
- button: `Экспорт в 1С`
- button: `Подтвердить`
- button: `OK`
- button: `Отмена`
- link: `Изделия -> /products`
- link: `{{ item.level|ru_level }} -> /products?level={{ item.level }}`
- link: `Сгенерировать ТК -> /items/{{ item.id }}/generate`
- link: `+ Извещение -> /notices/new?item_id={{ item.id }}`
- link: `← Назад -> /products?level={{ item.level }}`
- link: `Маршрут -> #ops`
- link: `Ресурсы -> #rs`
- link: `Состав -> #bom`
- link: `Детали -> #params`
- ... ещё 1

### `detail_new_placeholder.html` (1 элементов)
- link: `← К списку изделий -> /products`

### `help.html` (2 элементов)
- link: `Изделия -> /products`
- link: `эталоны -> /knowledge`

### `item_generate.html` (4 элементов)
- button: `Сгенерировать черновик`
- link: `Изделия -> /products`
- link: `{{ item.designation }} -> /detail/{{ item.id }}`
- link: `Отмена -> /detail/{{ item.id }}`

### `login.html` (3 элементов)
- input: `username`
- input: `password`
- button: `Войти`

### `metrics.html` (1 элементов)
- button: `Зафиксировать замер (точка на графике)`

### `notice_detail.html` (5 элементов)
- input: `decision`
- input: `notes`
- button: `Сгенерировать diff`
- button: `Подтвердить`
- link: `Извещения -> /notices`

### `notice_form.html` (10 элементов)
- input: `number`
- input: `date`
- input: `foundation_doc`
- input: `reason`
- input: `description`
- input: `affected_item_designation`
- input: `author`
- button: `Создать и обработать`
- link: `Извещения -> /notices`
- link: `Отмена -> /notices`

### `notices.html` (3 элементов)
- link: `Создать извещение -> /notices/new`
- link: `Открыть -> /notices/{{ n.id }}`
- link: `Создать извещение -> /notices/new`

### `products.html` (5 элементов)
- input: `q`
- input: `level`
- button: `Найти`
- link: `Сбросить -> /products`
- link: `Карточка → -> /detail/{{ it.id }}`

### `rs_export.html` (2 элементов)
- button: `Обновить`
- link: `Скачать XML -> /api/rs/download/${f.filename}`

### `settings.html` (8 элементов)
- input: `name`
- input: `display_name`
- input: `endpoint`
- input: `api_key`
- input: `cost`
- button: `Сохранить`
- link: `Назад -> /llm-admin`
- link: `Помощи -> /help`

## 6. Stats

- n_endpoints: 38
- n_templates: 18
- n_fk: 31
- n_tables: 34
- n_roles: 3
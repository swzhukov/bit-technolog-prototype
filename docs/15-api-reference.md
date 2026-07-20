# API Reference — полный справочник

> **Версия:** v0.4.12 (2026-07-20)
> **Базовый URL:** `http://your-server:8081`
> **Аутентификация:** на пилоте не используется (cookie `bit_role`)
> **Формат:** JSON / form-data / multipart
> **Версионирование:** нет (все endpoint'ы стабильны, см. `CHANGELOG.md`)

---

## Содержание

- [UI Pages (HTML)](#ui-pages-html)
- [Детали (CRUD)](#детали-crud)
- [Генерация (AI)](#генерация-ai)
- [Редактирование операций](#редактирование-операций)
- [Утверждение / Открытие](#утверждение--открытие)
- [Импорт / Экспорт](#импорт--экспорт)
- [Справочники](#справочники)
- [Отчёты пилота](#отчёты-пилота)
- [Админ-панель](#админ-панель)
- [Система](#система)

---

## UI Pages (HTML)

### `GET /` — Главная (список деталей)

**Query params:**
- `q=<text>` — поиск по обозначению/наименованию (с задержкой 300мс)
- `status=new|draft|approved|rejected` — фильтр по статусу
- `model=<model>` — фильтр по шасси
- `level=detail|product` — фильтр по уровню

**Response:** HTML (рендерится через Jinja)

**Права:** все роли

**Пример:**
```bash
curl http://localhost:8081/?q=АЦ-6,0
```

---

### `GET /detail/{detail_id}` — Карточка детали

**Path params:**
- `detail_id` — ID детали (например, `product-ac-6-40`)

**Response:** HTML (карточка с операциями, экономикой, AI-блоком, табами)

**Права:** все роли (но AI-блок виден только технолог/гл.технолог/админ)

**Пример:**
```bash
curl http://localhost:8081/detail/product-ac-6-40
```

---

### `GET /detail/{detail_id}/print` — Печатная форма

**Path params:**
- `detail_id` — ID детали

**Response:** HTML (для печати, с QR-кодом)

**Права:** все роли

---

### `GET /detail/{detail_id}/diff/{v_from}/{v_to}` — Сравнение версий

**Path params:**
- `detail_id` — ID детали
- `v_from` — начальная версия (целое число)
- `v_to` — конечная версия (целое число)

**Response:** HTML (diff таблица)

**Права:** все роли

**Пример:**
```bash
curl http://localhost:8081/detail/product-ac-6-40/diff/1/3
```

---

### `GET /detail/{detail_id}/history` — История изменений

**Response:** HTML (таблица событий)

**Права:** все роли

---

### `GET /history/{detail_id}` — то же что выше

**Алиас** для `/detail/{id}/history`

---

## Детали (CRUD)

### `GET /details/new` — Форма создания детали

**Response:** HTML (форма)

**Права:** технолог, гл.технолог, конструктор, админ

---

### `POST /api/details` — Создать деталь

**Content-Type:** `application/x-www-form-urlencoded` или `multipart/form-data`

**Form fields:**
- `designation` (required) — обозначение (например, `АЦ-6,0-40`)
- `name` — наименование
- `model` — модель (шасси)
- `chassis` — шасси
- `material` — материал
- `size_mm` — размер, мм (число)
- `mass_kg` — масса, кг (число)
- `surface_treatment` — поверхностная обработка

**Response:** `303 See Other` redirect на `/detail/{detail_id}`

**Права:** технолог, гл.технолог, конструктор, админ

**Пример:**
```bash
curl -X POST http://localhost:8081/api/details \
  -F "designation=АЦ-ХХХ" \
  -F "name=Новая деталь" \
  -F "model=АЦ-6,0-40" \
  -F "chassis=КАМАЗ-43118" \
  -F "material=Сталь 09Г2С" \
  -F "size_mm=100" \
  -F "mass_kg=5.0" \
  -F "surface_treatment=Грунт ГФ-021"
```

**Ответ:** HTTP 303, заголовок `Location: /detail/d-xxx`

---

### `POST /api/details/{detail_id}/rules` — Сохранить правила технолога

**Form fields:** произвольные key-value (попадают в `detail.tech_rules_json`)

**Response:** HTML фрагмент (status)

**Права:** технолог, гл.технолог, админ

---

## Генерация (AI)

### `POST /api/analyze` — AI задаёт уточняющие вопросы

**RBAC:** только `technologist`, `main_technologist`, `admin` (иначе 403)

**Form/JSON fields:**
- `detail_id` (required) — ID детали

**Response:** JSON
```json
{
  "questions": [
    {
      "question": "Какой тип сварки использовать?",
      "options": ["MIG", "TIG", "ручная дуговая"]
    }
  ]
}
```

**Стоимость:** ~0.5₽ (YandexGPT Lite, 200 токенов)

**Пример:**
```bash
curl -X POST http://localhost:8081/api/analyze \
  -F "detail_id=product-ac-6-40"
```

---

### `POST /api/draft-fast` — Быстрый draft (3 операции)

**RBAC:** только `technologist`, `main_technologist`, `admin`

**Form/JSON fields:**
- `detail_id` (required) — ID детали
- `answers` — JSON-строка с ответами на вопросы из `/api/analyze`

**Response:** JSON (draft операции)

**Стоимость:** ~1₽

**Пример:**
```bash
curl -X POST http://localhost:8081/api/draft-fast \
  -F "detail_id=product-ac-6-40" \
  -F 'answers={"q1":"MIG"}'
```

---

### `POST /api/refine` — Полная ТК (с учётом ответов)

**RBAC:** только `technologist`, `main_technologist`, `admin`

**Form/JSON fields:**
- `detail_id` (required)
- `answers` (required) — JSON-строка

**Response:** JSON (полный маршрут с операциями, материалами, временем)

**Стоимость:** ~3₽

---

### `POST /api/generate` — Генерация проекта ТК (старая кнопка)

**RBAC:** только `technologist`, `main_technologist`, `admin`

**Form/JSON/Query fields:**
- `detail_id` (required)

**Response:** HTML фрагмент (статус) или redirect

**Стоимость:** ~3₽ (если не в demo mode)

**Пример:**
```bash
curl -X POST http://localhost:8081/api/generate \
  -F "detail_id=product-ac-6-40"
```

---

## Редактирование операций

### `POST /api/edit/operation` — Редактировать поле операции

**Form fields:**
- `detail_id` (required)
- `op_index` (required) — индекс операции (0-based)
- `field` (required) — имя поля (`name`, `equipment`, `duration_hours`, и т.д.)
- `value` (required) — новое значение
- `reason` — причина изменения (для audit)

**Response:** JSON `{ok: true, version: <int>}`

**Права:** технолог, гл.технолог, админ

**Пример:**
```bash
curl -X POST http://localhost:8081/api/edit/operation \
  -F "detail_id=product-ac-6-40" \
  -F "op_index=0" \
  -F "field=name" \
  -F "value=010 Резка" \
  -F "reason=уточнение"
```

---

### `POST /api/edit/add-operation` — Добавить операцию

**Form fields:**
- `detail_id` (required)
- `name` (required) — название операции (например, `015 Гибка`)
- `equipment` — оборудование
- `duration_hours` — длительность, ч
- `department` — цех
- `workplace` — рабочее место
- `materials` — JSON-массив материалов
- `control_points` — JSON-массив контрольных точек

**Response:** JSON `{ok: true, version: <int>}`

---

### `POST /api/edit/delete-operation` — Удалить операцию (soft-delete)

**Form fields:**
- `detail_id` (required)
- `op_index` (required)
- `reason` (required) — причина удаления

**Response:** JSON `{ok: true, deleted_id: <int>}`

**Примечание:** операция не удаляется физически, а помечается `deleted_at`. Можно восстановить через `/api/edit/restore-operation`.

---

### `POST /api/edit/restore-operation` — Восстановить удалённую операцию

**Form fields:**
- `detail_id` (required)
- `deleted_id` (required) — ID удалённой операции (из `deleted_operations.id`)

**Response:** JSON `{ok: true, version: <int>}`

---

## Утверждение / Открытие

### `POST /api/approve` — Утвердить проект ТК

**Form fields:**
- `detail_id` (required)

**Response:** HTML фрагмент или JSON `{ok: true, status: "approved"}`

**Права:** технолог, гл.технолог, админ (для проекта ТК)

**Pre-conditions:**
- Все 4 галочки в чеклисте (`ck-1` ... `ck-4`) должны быть отмечены
- Эта проверка делается на клиенте (UI), серверная часть проверяет только статус

---

### `POST /api/approve-chief` — Утвердить как гл. технолог

**Form fields:**
- `detail_id` (required)
- `comment` — комментарий

**Response:** JSON `{ok: true, status: "approved_chief"}`

**Права:** гл.технолог, админ

**Pre-conditions:** деталь должна быть в статусе "draft" (утверждена технологом)

---

### `POST /api/approve-workshop` — Утвердить как нач. цеха

**Form fields:**
- `detail_id` (required)

**Response:** JSON `{ok: true, status: "approved_workshop"}`

**Права:** нач.цеха, админ

**Pre-conditions:** деталь должна быть в статусе "approved" (утверждена гл.технологом)

---

### `POST /api/reopen` — Вернуть в работу (откатить утверждение)

**Form fields:**
- `detail_id` (required)
- `reason` — причина возврата

**Response:** JSON `{ok: true, status: "draft"}`

**Права:** технолог, гл.технолог, админ

---

## Импорт / Экспорт

### `POST /api/import/tk` — Импорт техкарт

**Content-Type:** `multipart/form-data` (файл) или `application/json` (тело)

**Form fields:**
- `file` — файл (.xlsx, .csv, .json, .pdf)
- или тело JSON: `{"details": [{...}, {...}]}`

**Валидация:**
- Проверка magic bytes (защита от .exe переименованного в .pdf)
- Обязательные поля: `designation`
- `mass_kg` должно быть числом
- `size_mm` должно быть числом

**Response:** JSON
```json
{
  "created": 5,
  "skipped": 1,
  "errors": []
}
```

**Права:** технолог, гл.технолог, админ

**Пример (JSON):**
```bash
curl -X POST http://localhost:8081/api/import/tk \
  -H "Content-Type: application/json" \
  -d '{"details":[{"designation":"X","name":"Test","model":"A","chassis":"B","material":"C","size_mm":"100","mass_kg":5}]}'
```

---

### `POST /api/export/pdf` — Экспорт в PDF

**Form fields:**
- `detail_id` (required)

**Response:** `application/pdf` (binary)

**Пример:**
```bash
curl -X POST http://localhost:8081/api/export/pdf \
  -F "detail_id=product-ac-6-40" \
  -o document.pdf
```

---

### `POST /api/export/excel` — Экспорт в Excel (.xlsx)

**Form fields:**
- `detail_id` (required)

**Response:** `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` (binary)

---

### `GET /api/export/onec-csv` — Экспорт в 1С:CSV

**Query params:**
- `detail_id` (required)

**Response:** `text/csv; charset=utf-8`

**Пример:**
```bash
curl "http://localhost:8081/api/export/onec-csv?detail_id=product-ac-6-40" \
  -o for_1c.csv
```

---

### `GET /api/import/stats` — Статистика импорта

**Response:** JSON `{total_imports: int, last_import: datetime, errors: [...]}`

---

## Справочники

### `GET /equipment` — Справочник оборудования

**Response:** HTML (таблица с поиском)

**Права:** все роли

---

### `GET /materials` — Справочник материалов

**Response:** HTML

---

### `GET /iot` — Справочник ИОТ (инструкции по охране труда)

**Response:** HTML

---

### `GET /benchmarks` — Бенчмарки (эталонные трудоёмкости)

**Response:** HTML (таблица: операция, среднее время, мин, макс, источник)

---

## Отчёты пилота

### `GET /pilot` — Pilot dashboard (главная)

**Response:** HTML (KPI, метрики, графики)

**Права:** все роли (но админ видит больше)

**Метрики:**
- Всего деталей
- Принято / отклонено
- Acceptance rate
- Среднее время на деталь
- Стоимость LLM за сегодня / за месяц

---

### `GET /pilot/learning` — Дашборд обучения (тренд по неделям)

**Query params:**
- `weeks` (default 4) — количество недель

**Response:** HTML (графики acceptance rate, LLM стоимости, количества ТК)

---

### `GET /api/pilot/learning` — JSON для графиков

**Query params:** `weeks` (default 4)

**Response:** JSON
```json
{
  "metrics": [
    {"week": "2026-W28", "accepted": 12, "rejected": 3, "cost_rub": 45.5, "count": 15}
  ]
}
```

---

### `GET /pilot/report?days=N` — Текстовый отчёт за N дней

**Query params:** `days` (default 7)

**Response:** HTML (или markdown при `?format=md`)

**Метрики:** аналогично `/pilot` + детализация по деталям

---

## Админ-панель

> **Все endpoint'ы ниже требуют роль `admin`** (иначе 403)

### `GET /admin` — Главная админки

**Response:** HTML (метрики системы, статус сервисов)

---

### `GET /admin/users` — Управление пользователями

**Response:** HTML (таблица пользователей)

---

### `GET /admin/login-log` — Лог входов

**Query params:** `days` (default 30)

**Response:** HTML (таблица событий входа)

---

### `GET /admin/llm-calls` — Все вызовы LLM

**Query params:** `days` (default 7), `detail_id`, `status`

**Response:** HTML (таблица с временем, моделью, токенами, стоимостью, ошибкой)

---

### `GET /admin/settings` — Настройки системы

**Response:** HTML (формы: YandexGPT API key, Telegram bot token, SMTP)

---

### `POST /admin/settings` — Сохранить настройку

**Form fields:**
- `key` (required) — имя настройки (например, `llm_api_key`)
- `value` — значение (зашифровано Fernet перед сохранением)

**Response:** JSON `{ok: true}`

---

### `GET /admin/errors` — Последние 50 ошибок сервера (V8-18)

**Response:** HTML (таблица с timestamp, endpoint, error message, debugging_id)

**Примечание:** debugging_id = первые 8 символов UUID. Ищите в логах.

---

### `GET /admin/system` — Состояние системы

**Response:** HTML (БД, RAG, диск, процессы)

---

### `POST /api/admin/backup` — Создать бэкап (rate-limited: 1/час)

**Response:** HTML (ссылка на скачивание .db файла)

**Rate limit:** 1 запрос в час (настраивается через `PILOT_BACKUP_RATE_LIMIT`)

---

## Система

### `GET /health` — Health-check

**Response:** JSON
```json
{
  "status": "ok",
  "version": "0.4.12",
  "build_date": "2026-07-20",
  "git_commit": "a666645",
  "uptime_sec": 86400,
  "dependencies": {
    "llm": "auth_error",
    "telegram": "not_configured",
    "smtp": "not_configured"
  },
  "db": {
    "details_count": 25,
    "drafts_count": 18,
    "draft_versions_count": 47
  },
  "cost_anomaly": "ok"
}
```

**Права:** все (для мониторинга)

---

### `POST /api/role/switch` — Сменить роль

**Form/JSON fields:**
- `role` (required) — одна из 7 ролей

**Response:** JSON `{ok: true, role: "...", name: "..."}`

**Cookie:** устанавливает `bit_role` (без `HttpOnly`, чтобы JS мог прочитать)

**Пример:**
```bash
curl -X POST http://localhost:8081/api/role/switch \
  -F "role=admin" \
  -c cookies.txt
```

---

### `GET /favicon.ico` — Иконка

**Response:** PNG (1x1 transparent) + базовая SVG в header

---

### `GET /api/economics/{detail_id}` — Экономика (JSON)

**Response:** JSON (расчёт себестоимости и рекомендуемой цены)

**Пример:**
```bash
curl http://localhost:8081/api/economics/product-ac-6-40
```

---

### `GET /404` — Кастомная 404 страница

Любой несуществующий URL → `404 Not Found` с навигацией.

---

## Коды ошибок

| Код | Когда | Что делать |
|---|---|---|
| 200 | Успех | OK |
| 303 | Redirect (после создания) | Следовать на `Location` |
| 400 | Невалидные данные | Проверить формат, обязательные поля |
| 403 | Нет прав (роль) | Сменить роль через `/api/role/switch` |
| 404 | Не найдено | Проверить ID |
| 422 | Unprocessable Entity (FastAPI default) | Проверить формат JSON |
| 429 | Превышен дневной лимит LLM (200₽) | Подождать до завтра или увеличить лимит |
| 500 | Внутренняя ошибка сервера | Проверить `/admin/errors`, debugging_id в логах |

---

## CSRF, CSP, Rate Limiting

- **CSRF:** ВКЛЮЧЕН по умолчанию (для production). Для тестов — `PILOT_CSRF_DISABLED=true`
- **CSP:** `default-src 'self'`, `unsafe-inline` для htmx/onclick
- **Rate limiting:** в памяти (не сохраняется между перезапусками)
  - `/api/generate` — 10/мин
  - `/api/import/tk` — 5/5мин
  - `/api/admin/backup` — 1/час
- **Opt-out:** `PILOT_RATELIMIT_DISABLED=true` (для тестов)

---

## Примеры типичных сценариев

### Создать деталь и сгенерировать ТК (curl)

```bash
# 1. Сменить роль на технолога
curl -X POST http://localhost:8081/api/role/switch \
  -F "role=technologist" -c cookies.txt

# 2. Создать деталь
curl -X POST http://localhost:8081/api/details \
  -F "designation=АЦ-ХХХ" -F "name=Test" -F "model=АЦ-6,0-40" \
  -F "chassis=КАМАЗ-43118" -F "material=Сталь 09Г2С" \
  -F "size_mm=100" -F "mass_kg=5" -F "surface_treatment=Грунт" \
  -b cookies.txt -c cookies.txt
# → 303 Location: /detail/d-xxx

# 3. Сгенерировать draft
curl -X POST http://localhost:8081/api/generate \
  -F "detail_id=d-xxx" -b cookies.txt -c cookies.txt
# → HTML фрагмент

# 4. Утвердить
curl -X POST http://localhost:8081/api/approve \
  -F "detail_id=d-xxx" -b cookies.txt -c cookies.txt
```

### Импортировать JSON с деталями

```bash
cat > details.json <<EOF
{
  "details": [
    {"designation": "А.001", "name": "Деталь 1", "model": "АЦ-6,0-40", "chassis": "КАМАЗ", "material": "Сталь", "size_mm": "100", "mass_kg": 5},
    {"designation": "А.002", "name": "Деталь 2", "model": "АЦ-6,0-40", "chassis": "КАМАЗ", "material": "Сталь", "size_mm": "200", "mass_kg": 10}
  ]
}
EOF

curl -X POST http://localhost:8081/api/import/tk \
  -H "Content-Type: application/json" \
  -d @details.json
# → {"created": 2, "skipped": 0}
```

### Экспортировать в 1С:CSV

```bash
curl "http://localhost:8081/api/export/onec-csv?detail_id=product-ac-6-40" \
  -o for_1c.csv
```

---

## См. также

- [`02-architecture.md`](02-architecture.md) — как всё устроено внутри
- [`13-developer-guide.md`](13-developer-guide.md) — как добавить новый endpoint
- [`15-api-reference.md`](15-api-reference.md) — этот документ
- [`18-troubleshooting.md`](18-troubleshooting.md) — если что-то не работает

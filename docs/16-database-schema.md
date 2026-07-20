# Схема базы данных

> **Версия:** v0.4.12 (2026-07-20)
> **СУБД:** SQLite 3.11+ (WAL mode)
> **Расположение:** `/opt/beget/bit-technolog/bit_technolog.db` (на сервере)
> **Миграции:** `db.py::init_db()` (CREATE TABLE IF NOT EXISTS) + ручные ALTER

---

## Общая информация

- **Режим журналирования:** WAL (Write-Ahead Logging) — для параллельного чтения во время записи
- **Размер:** ~5-10 МБ на 100 деталей с 5 операциями каждая
- **Резервное копирование:** ежедневно 3:00 через `backup.sh` → `/opt/beget/backups/`
- **Шифрование:** опционально через gpg (`BACKUP_GPG_RECIPIENT` env)
- **Retention:** 30 дней бэкапов (по умолчанию), cleanup через `cleanup_old_backups()` в `backup.sh`

**Прямой доступ (CLI):**
```bash
sqlite3 /opt/beget/bit-technolog/bit_technolog.db
> .tables
> .schema details
> SELECT COUNT(*) FROM details;
```

Если sqlite3 CLI не установлен (как на Beget VPS), используйте Python:
```bash
cd /opt/beget/bit-technolog && python3 -c "
import sqlite3
conn = sqlite3.connect('bit_technolog.db')
for row in conn.execute('SELECT id, designation FROM details LIMIT 5'):
    print(row)
conn.close()
"
```

---

## Список таблиц (21 шт.)

| Таблица | Назначение | Записей на пилоте (примерно) |
|---|---|---|
| `details` | Детали (от конструкторов) | 25 (seed) + 5-10/неделю |
| `drafts` | Текущий draft (1 на деталь) | =кол-во деталей с draft |
| `draft_versions` | История версий draft | 3-5 на деталь |
| `edits` | История правок операций | 10-30 на деталь |
| `rules` | Правила технолога (учитываются AI) | 0-3 на деталь |
| `equipment` | Справочник оборудования | ~100 |
| `materials` | Справочник материалов | ~50 |
| `departments` | Цеха | 3 (Цех 1, Цех 2, Цех 3) |
| `iot` | Инструкции по охране труда | ~30 |
| `benchmarks` | Эталонные трудоёмкости | ~50 |
| `history` | История изменений (audit) | 100+ на деталь |
| `deleted_operations` | Soft-delete операций | 0-5 на деталь |
| `step_answers` | Ответы на вопросы AI (localStorage + сервер) | 1 на деталь |
| `pilot_metrics` | Агрегированные метрики пилота | 1 запись/день |
| `llm_calls` | Логи вызовов LLM (цена, токены, ошибки) | 50-200/день |
| `professions` | Справочник профессий | ~20 |
| `resource_specs` | Спецификации ресурсов (для 1С) | ~30 |
| `drawings` | Чертежи (пути к файлам) | 0-1 на деталь |
| `pilot_users` | Пользователи (для будущей авторизации) | 5-10 |
| `audit_logins` | Лог входов | 1/день на пользователя |
| `app_settings` | Настройки (зашифрованы Fernet) | 10-20 |

---

## Схема таблиц

### `details` — детали (главная таблица)

```sql
CREATE TABLE details (
    id TEXT PRIMARY KEY,                  -- 'd-xxxxx' или 'product-ac-6-40'
    designation TEXT NOT NULL,            -- 'АЦ-6,0-40'
    name TEXT,                            -- 'Автоцистерна пожарная...'
    model TEXT,                           -- 'АЦ-6,0-40' (шасси/модель)
    chassis TEXT,                         -- 'КАМАЗ-43118'
    material TEXT,                        -- 'Сталь 09Г2С'
    size_mm REAL,                         -- 100
    mass_kg REAL,                         -- 5.0
    surface_treatment TEXT,               -- 'Грунт ГФ-021'
    level TEXT DEFAULT 'detail',          -- 'detail' | 'product' | 'assembly'
    parent_id TEXT,                       -- для иерархии (если сборка)
    drawing_path TEXT,                    -- '/drawings/detail-001.pdf'
    drawing_format TEXT,                  -- 'pdf' | 'dxf' | 'cdw'
    material_cost_rub REAL,               -- 500.0 (для экономики)
    hourly_rate_rub REAL,                 -- 800.0 (ставка цеха)
    overhead_rate_pct REAL,               -- 30.0 (накладные %)
    tech_rules_json TEXT,                 -- JSON: правила для AI
    rag_keywords TEXT,                    -- через запятую, для RAG
    created_at TEXT NOT NULL,             -- '2026-07-20T05:00:00'
    updated_at TEXT NOT NULL,
    created_by TEXT                       -- роль пользователя
);

CREATE INDEX idx_details_model ON details(model);
CREATE INDEX idx_details_chassis ON details(chassis);
CREATE INDEX idx_details_status ON details(status);  -- если есть (в JOIN с drafts)
CREATE INDEX idx_details_level ON details(level);
```

**Связи:**
- `parent_id` → `details.id` (self-FK, иерархия деталей)
- `drafts.detail_id` → `details.id` (1:1)
- `history.detail_id` → `details.id` (1:N)

---

### `drafts` — текущий draft (1 на деталь)

```sql
CREATE TABLE drafts (
    detail_id TEXT PRIMARY KEY,           -- FK → details.id
    llm_output TEXT NOT NULL,             -- JSON: операции, экономика, warnings
    status TEXT NOT NULL DEFAULT 'draft', -- 'new' | 'draft' | 'approved' | 'rejected'
    status_ext TEXT,                      -- 'review' | 'returned' (для workflow)
    author TEXT,                          -- роль создавшего
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    approved_at TEXT,                     -- когда утверждена
    approved_by TEXT,                     -- кто утвердил
    FOREIGN KEY (detail_id) REFERENCES details(id) ON DELETE CASCADE
);
```

**Статусы:**
- `new` — деталь без draft
- `draft` — проект ТК (AI сгенерировал, но не утверждён)
- `approved` — утверждён технологом
- `approved_chief` — утверждён гл.технологом
- `approved_workshop` — утверждён нач.цеха (финальный)
- `rejected` — отклонён

---

### `draft_versions` — история версий

```sql
CREATE TABLE draft_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detail_id TEXT NOT NULL,
    version INTEGER NOT NULL,             -- 1, 2, 3, ...
    operations_json TEXT NOT NULL,        -- JSON: операции
    source TEXT,                          -- 'llm' | 'human' | 'hybrid'
    notes TEXT,                           -- комментарий
    author TEXT,                          -- роль
    created_at TEXT NOT NULL,
    UNIQUE(detail_id, version),
    FOREIGN KEY (detail_id) REFERENCES details(id) ON DELETE CASCADE
);
```

**Каждое изменение** (генерация, edit, add/delete) создаёт новую версию.

---

### `edits` — история правок операций

```sql
CREATE TABLE edits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detail_id TEXT NOT NULL,
    op_index INTEGER,                     -- индекс операции (0-based)
    field TEXT,                           -- 'name' | 'equipment' | ...
    old_value TEXT,                       -- предыдущее значение
    new_value TEXT,                       -- новое значение
    reason TEXT,                          -- причина правки
    author TEXT,                          -- роль
    created_at TEXT NOT NULL,
    FOREIGN KEY (detail_id) REFERENCES details(id) ON DELETE CASCADE
);
```

**Используется для** diff между версиями и для audit (кто что менял).

---

### `deleted_operations` — soft-delete

```sql
CREATE TABLE deleted_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detail_id TEXT NOT NULL,
    op_data_json TEXT NOT NULL,           -- JSON операции
    op_index INTEGER,                     -- на какой позиции была
    reason TEXT,
    deleted_by TEXT,
    deleted_at TEXT NOT NULL,
    restored_at TEXT,                     -- если восстановлена
    restored_by TEXT
);
```

Операция **не удаляется физически** — попадает сюда. Можно восстановить через `/api/edit/restore-operation`.

---

### `llm_calls` — лог вызовов LLM (для метрик и админа)

```sql
CREATE TABLE llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detail_id TEXT,                       -- NULL если не связано с деталью
    model TEXT,                           -- 'yandexgpt-lite' | 'mock'
    system_msg TEXT,                      -- system prompt
    user_prompt TEXT,                     -- user prompt
    response TEXT,                        -- полный ответ
    success INTEGER,                      -- 0 | 1
    error TEXT,                           -- error message если success=0
    tokens_input INTEGER,
    tokens_output INTEGER,
    cost_rub REAL,                        -- стоимость
    duration_ms INTEGER,                  -- время выполнения
    created_at TEXT NOT NULL
);

CREATE INDEX idx_llm_calls_created_at ON llm_calls(created_at);
CREATE INDEX idx_llm_calls_detail_id ON llm_calls(detail_id);
```

**Retention:** 90 дней (через `cleanup_old_records()` в `admin.py`).

---

### `history` — журнал изменений (audit)

```sql
CREATE TABLE history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detail_id TEXT NOT NULL,
    event_type TEXT NOT NULL,             -- 'detail_created' | 'draft_generated' | 'edit_operation' | 'approve' | 'reopen' | ...
    event_data_json TEXT,                 -- JSON с деталями события
    author TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (detail_id) REFERENCES details(id) ON DELETE CASCADE
);

CREATE INDEX idx_history_detail_id ON history(detail_id);
CREATE INDEX idx_history_created_at ON history(created_at);
```

**Retention:** 365 дней.

**Типы событий:**
- `detail_created` — деталь создана
- `draft_generated` — AI сгенерировал draft
- `edit_operation` — изменена операция
- `add_operation` — добавлена операция
- `delete_operation` — удалена операция
- `restore_operation` — восстановлена операция
- `approve` — утверждена (технологом)
- `approve_chief` — утверждена гл.технологом
- `approve_workshop` — утверждена нач.цеха
- `reopen` — возвращена в работу
- `import` — импортирована
- `export` — экспортирована

---

### `pilot_users` — пользователи (для будущей авторизации)

```sql
CREATE TABLE pilot_users (
    id TEXT PRIMARY KEY,                  -- 'u-xxx'
    username TEXT UNIQUE NOT NULL,        -- 's.zhukov'
    full_name TEXT,                       -- 'Жуков Сергей'
    role TEXT NOT NULL,                   -- 'technologist' | ...
    password_hash TEXT,                   -- bcrypt(sha256(salt + password))
    salt TEXT,                            -- 32 hex chars
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    last_login TEXT
);
```

**Сейчас не используется** (на пилоте роль через cookie). В будущем — LDAP/AD.

---

### `audit_logins` — лог входов

```sql
CREATE TABLE audit_logins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    username TEXT,
    ip_address TEXT,
    user_agent TEXT,
    success INTEGER,                      -- 0 | 1
    error TEXT,
    created_at TEXT NOT NULL
);
```

**Retention:** 180 дней.

---

### `app_settings` — настройки (Fernet-encrypted)

```sql
CREATE TABLE app_settings (
    key TEXT PRIMARY KEY,                 -- 'llm_api_key'
    value TEXT,                           -- Fernet-encrypted
    description TEXT,
    updated_at TEXT NOT NULL,
    updated_by TEXT
);
```

**Зашифровано** через Fernet (AES-128-CBC + HMAC-SHA256).
Ключ хранится в `.master_key` (вне БД, в `.gitignore`).

**Группы настроек:**
- `llm_*` — YandexGPT (api_key, folder_id, model, daily_limit_rub)
- `telegram_*` — Telegram bot (token, chat_id)
- `smtp_*` — Email (host, port, user, password)
- `backup_*` — бэкапы (gpg_recipient, retention_days)
- `pilot_*` — пилот (start_date, end_date, target_acceptance_rate)

---

### `step_answers` — ответы на вопросы AI

```sql
CREATE TABLE step_answers (
    detail_id TEXT PRIMARY KEY,
    answers_json TEXT NOT NULL,           -- {"q1": "MIG", "q2": "ручная дуговая"}
    updated_at TEXT NOT NULL
);
```

**Дубликат localStorage** — если пользователь потерял браузер, ответы сохранятся на сервере.

---

### Остальные таблицы (кратко)

#### `equipment`
```sql
CREATE TABLE equipment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    model TEXT,
    department TEXT,                      -- 'Цех 1' | 'Цех 2' | 'Цех 3'
    workplace TEXT,                       -- 'РМ 1', 'РМ 2'
    power_kw REAL,
    hourly_rate_rub REAL,
    notes TEXT,
    UNIQUE(name, model)
);
```

#### `materials`
```sql
CREATE TABLE materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                   -- 'Сталь 09Г2С'
    gost TEXT,                            -- 'ГОСТ 19281-89'
    category TEXT,                        -- 'Сталь' | 'Алюминий' | 'Пластик'
    density_kg_per_m3 REAL,
    cost_per_kg_rub REAL,
    synonyms TEXT,                        -- 'ст3,09г2с,09Г2С,St3' (через запятую, для лемматизации)
    notes TEXT,
    UNIQUE(name)
);
```

#### `departments`
```sql
CREATE TABLE departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,            -- 'Цех 1', 'Цех 2', 'Цех 3'
    hourly_rate_rub REAL DEFAULT 800.0,
    overhead_rate_pct REAL DEFAULT 30.0
);
```

#### `iot` (инструкции по охране труда)
```sql
CREATE TABLE iot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,                     -- 'ИОТ-001'
    operation_type TEXT,                  -- 'Сварка', 'Резка', 'Гибка'
    description TEXT,
    hazards TEXT,                         -- 'Искры, ультрафиолет'
    safety_measures TEXT,                 -- 'Очки, перчатки'
    source TEXT                           -- 'ГОСТ 12.3.002'
);
```

#### `benchmarks` (эталонные трудоёмкости)
```sql
CREATE TABLE benchmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_type TEXT,                  -- 'Резка', 'Сварка', 'Гибка'
    material_category TEXT,               -- 'Сталь' | 'Алюминий'
    avg_duration_hours REAL,
    min_duration_hours REAL,
    max_duration_hours REAL,
    source TEXT,                          -- 'СНиП' | 'Опыт Техинкома'
    notes TEXT
);
```

#### `professions`
```sql
CREATE TABLE professions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,                     -- 'Сварщик 3 разряда'
    name TEXT,
    category TEXT,                        -- 'Основная' | 'Вспомогательная'
    hourly_rate_rub REAL
);
```

#### `resource_specs` (спецификации для 1С)
```sql
CREATE TABLE resource_specs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detail_id TEXT,
    material_id INTEGER,
    equipment_id INTEGER,
    quantity REAL,
    unit TEXT,                            -- 'кг' | 'м' | 'шт'
    notes TEXT,
    FOREIGN KEY (detail_id) REFERENCES details(id) ON DELETE CASCADE
);
```

#### `drawings`
```sql
CREATE TABLE drawings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detail_id TEXT,
    file_path TEXT NOT NULL,              -- '/drawings/АЦ-ХХХ.pdf'
    format TEXT,                          -- 'pdf' | 'dxf' | 'cdw'
    file_size_kb INTEGER,
    uploaded_at TEXT,
    uploaded_by TEXT
);
```

#### `pilot_metrics` (агрегаты по дням)
```sql
CREATE TABLE pilot_metrics (
    date TEXT PRIMARY KEY,                -- '2026-07-20'
    details_created INTEGER,
    drafts_generated INTEGER,
    drafts_accepted INTEGER,
    drafts_rejected INTEGER,
    llm_calls INTEGER,
    llm_cost_rub REAL,
    avg_time_per_detail_min REAL,
    acceptance_rate REAL                  -- 0.0-1.0
);
```

**Заполняется** ежедневно cron'ом `/opt/beget/bit-technolog/cron/daily_metrics.py`.

#### `rules` (правила технолога)
```sql
CREATE TABLE rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detail_id TEXT,
    rule_text TEXT,
    priority INTEGER,                     -- 1-10 (чем выше, тем важнее для AI)
    created_by TEXT,
    created_at TEXT
);
```

---

## Полезные запросы

### Топ-10 деталей по количеству операций

```sql
SELECT d.designation, d.name,
       (SELECT COUNT(*) FROM draft_versions WHERE detail_id = d.id) AS versions
FROM details d
ORDER BY versions DESC
LIMIT 10;
```

### Acceptance rate за неделю

```sql
SELECT
  DATE(created_at) AS day,
  COUNT(*) AS total,
  SUM(CASE WHEN event_type LIKE 'approve%' THEN 1 ELSE 0 END) AS approved
FROM history
WHERE created_at >= DATE('now', '-7 days')
GROUP BY day;
```

### Самые дорогие вызовы LLM

```sql
SELECT detail_id, model, cost_rub, tokens_input, tokens_output, created_at
FROM llm_calls
ORDER BY cost_rub DESC
LIMIT 10;
```

### Неактивные пользователи (за 30 дней)

```sql
SELECT username, last_login
FROM pilot_users
WHERE last_login < DATE('now', '-30 days') OR last_login IS NULL;
```

### Детали, которые никогда не генерировали draft

```sql
SELECT d.id, d.designation
FROM details d
LEFT JOIN drafts dr ON dr.detail_id = d.id
WHERE dr.detail_id IS NULL;
```

---

## Миграции

**Стратегия:** `CREATE TABLE IF NOT EXISTS` + ручные `ALTER TABLE` (если нужны новые колонки).

**Пример миграции** (если нужна новая колонка):
```python
# db.py
def migrate_v1_to_v2():
    conn = get_conn()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(details)").fetchall()]
    if 'cost_anomaly_score' not in cols:
        conn.execute("ALTER TABLE details ADD COLUMN cost_anomaly_score REAL")
    conn.commit()
    conn.close()
```

**Применяется** в `init_db()` после `CREATE TABLE IF NOT EXISTS`.

---

## Бэкапы

### Ручной бэкап

```bash
cd /opt/beget/bit-technolog
bash backup.sh
# Создаёт /opt/beget/backups/bit_technolog_YYYY-MM-DD_HH-MM.db
```

### С шифрованием (gpg)

```bash
export BACKUP_GPG_RECIPIENT="admin@tehincom.ru"
bash backup.sh
# Создаёт .db.gpg файл
```

Для расшифровки:
```bash
gpg --decrypt bit_technolog_2026-07-20_03-00.db.gpg > restored.db
```

### Автоматический (cron)

```bash
# /etc/cron.d/bit-technolog
0 3 * * * cd /opt/beget/bit-technolog && bash backup.sh >> /var/log/bit-technolog/backup.log 2>&1
```

### Retention

```bash
# В backup.sh (по умолчанию)
KEEP_DAYS=30
find /opt/beget/backups -name "bit_technolog_*.db*" -mtime +$KEEP_DAYS -delete
```

---

## Производительность

**Размер БД:** ~5-10 МБ на 100 деталей. Растёт медленно.

**Индексы:** созданы на часто запрашиваемых колонках (см. выше). Дополнительные — по необходимости.

**Оптимизации:**
- WAL mode (включён в `init_db()` через `PRAGMA journal_mode=WAL`)
- Prepared statements (все запросы используют `?` placeholder)
- Batch inserts (для импорта)

**Если тормозит:**
```sql
EXPLAIN QUERY PLAN SELECT * FROM details WHERE model = 'АЦ-6,0-40';
-- Должен использовать idx_details_model
```

Если не использует индекс — проверьте, что `ANALYZE` выполнен:
```sql
ANALYZE;
```

---

## См. также

- [`02-architecture.md`](02-architecture.md) — общая архитектура
- [`12-admin-guide.md`](12-admin-guide.md) — гайд для админа (включая работу с БД)
- [`17-deployment.md`](17-deployment.md) — deployment и cron
- [`19-security-compliance.md`](19-security-compliance.md) — 152-ФЗ, retention
- [`18-troubleshooting.md`](18-troubleshooting.md) — типичные проблемы с БД

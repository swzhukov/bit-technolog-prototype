# БИТ.Технолог — Архитектура MVP v0.4.9 (actual state)

> **Дата обновления:** 2026-07-19
> **Назначение:** детальная техническая архитектура для разработки.
> **Контекст:** docs/01-product-design.md, docs/05-techinkom-context.md, docs/03-training-architecture.md, docs/04-pilot-roadmap.md.
> **Стек:** Python 3.12, FastAPI, Jinja2+HTMX, SQLite (WAL), scikit-learn TF-IDF + pymorphy2, cryptography (Fernet), bcrypt. On-premise.

> **v0.4.9 actual state** (отличается от v0.1):
> - ✅ SQLite вместо PostgreSQL (для пилота; можно перенести в PostgreSQL в enterprise-режиме)
> - ✅ TF-IDF + cosine вместо ChromaDB (on-prem, бесплатно; baseline)
> - ✅ pymorphy2 лемматизация + маппинг синонимов (F16.2)
> - ❌ Watcher КОМПАС-3D — отложен (F12, post-pilot)
> - ❌ 1C OData — отложен (F14, post-pilot; пока CSV/XML экспорт)
> - ❌ Redis Queue — не нужен (FastAPI sync, monolithic)
> - ❌ Docker Compose — отложен (Sprint 5 enterprise; пока systemd на Beget VPS)
> - ❌ NGINX — не используется (80/443 на Beget заняты docker-proxy, поэтому uvicorn напрямую на 8081)

---

## 1. ОБЩАЯ СХЕМА

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           ВНЕШНИЕ СИСТЕМЫ                                     │
│                                                                              │
│  ┌────────────────────┐    ┌────────────────────┐    ┌────────────────────┐  │
│  │  1С:ERP 2.5         │    │  КОМПАС-3D         │    │  LLM API            │  │
│  │  (мастер НСИ)       │    │  (конструктор)     │    │  (YandexGPT Lite)   │  │
│  │                     │    │                    │    │                     │  │
│  │  - Экспорт CSV/XML  │    │  - .m3d / .cdw     │    │  - OpenAI API       │  │
│  │  - Импорт РС (XML)  │    │  - Watch-папка     │    │  - YandexGPT        │  │
│  │                     │    │  (отложен F12)     │    │  - BYOK             │  │
│  └─────────┬───────────┘    └─────────┬──────────┘    └─────────┬───────────┘  │
│            │ CSV/XML                  │ (post-pilot)             │ HTTPS        │
└────────────┼───────────────────────────┼───────────────────────────┼──────────┘
             │                           │                            │
             ▼                           ▼                            ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         BIT-TECHNOLOG APP                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  WATCHER (file watcher)                                                │   │
│  │  - Следит за 3-5 watch-папками                                         │   │
│  │  - Парсит .m3d/.cdw → JSON свойства                                   │   │
│  │  - Публикует событие "new_detail" / "detail_changed" в Redis Queue   │   │
│  └─────────────────────────┬────────────────────────────────────────────┘   │
│                             │ Redis Queue                                    │
│                             ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  1C CONNECTOR                                                         │   │
│  │  - Чтение НСИ из 1С (OData клиент)                                    │   │
│  │  - Кеш НСИ в SQLite                                                  │   │
│  │  - Инвалидация кеша (cron + push)                                    │   │
│  │  - Запись РС в 1С (HTTP POST)                                        │   │
│  │  - Маппинг кодов 1С ↔ наш ID                                         │   │
│  └─────────────────────────┬────────────────────────────────────────────┘   │
│                             │ локальный кеш                                  │
│                             ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  LLM-AGENT (FastAPI worker)                                           │   │
│  │  - Получает: свойства + аналоги + кеш НСИ + правила                 │   │
│  │  - Few-shot: 4c85941a (Кедр-300, операции 015-040)                   │   │
│  │  - Промт v0.2 → JSON по 6 вкладкам                                   │   │
│  │  - Latency: ≤ 30 сек                                                  │   │
│  └─────────────────────────┬────────────────────────────────────────────┘   │
│                             │ результат (draft)                              │
│                             ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  RAG INDEX (ChromaDB / SQLite + embeddings)                          │   │
│  │  - Эмбеддинги: техкарты 4c85941a, 24f5ab23 + РС из 1С               │   │
│  │  - Поиск аналогов по обозначению/материалу/габаритам                │   │
│  │  - Match score 0-1                                                    │   │
│  └─────────────────────────┬────────────────────────────────────────────┘   │
│                             │ топ-3 аналога                                   │
│                             ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  WEB UI (HTMX + FastAPI + Jinja2)                                    │   │
│  │  - Список деталей (фильтры, статусы)                                 │   │
│  │  - Карточка детали (6 вкладок)                                       │   │
│  │  - Действия: Утвердить / В 1С / Обновить                             │   │
│  │  - Экран синхронизации с 1С                                          │   │
│  │  - Справочник AI-метаданных                                          │   │
│  └─────────────────────────┬────────────────────────────────────────────┘   │
│                             │ user actions                                   │
│                             ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  POSTGRESQL (наша БД для AI-метаданных, не мастер)                   │   │
│  │  - Таблица drafts (черновики ТК)                                      │   │
│  │  - Таблица ai_metadata (confidence, source, warnings)                 │   │
│  │  - Таблица history (audit log)                                        │   │
│  │  - Таблица cache (кеш НСИ из 1С)                                     │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  NGINX / Caddy (reverse proxy, TLS, статика)                        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. КОМПОНЕНТЫ

### 2.1. Watcher (file watcher)

**Назначение:** следит за watch-папками конструкторов, парсит .m3d/.cdw, публикует события.

**Технологии:**
- Python 3.11+
- `watchdog` — кросс-платформенный file watcher
- КОМПАС-3D API (COM-объект) или парсинг .m3d (бинарный формат, нужна библиотека)
- Redis Queue (`rq`) для публикации событий

**Интерфейсы:**
- File watcher event: `(path: str, event: str, hash: str)`
- Публикует в Redis: `{event: "new_detail"|"changed", detail_id: uuid, properties: {...}}`

**Свойства детали (из КОМПАС-3D):**
```json
{
  "name": "Кронштейн крепления насоса",
  "designation": "КРН-001-АЦ6",
  "material": "Сталь 09Г2С",
  "mass_kg": 12.5,
  "dimensions_mm": {"x": 250, "y": 180, "z": 80},
  "gost": "ГОСТ 19903-2015",
  "surface_treatment": "покраска",
  "chassis": "КАМАЗ 43118",
  "file_path": "/path/to/KRN-001-AC6.m3d",
  "file_hash": "sha256:...",
  "created_at": "ISO8601"
}
```

**Fallback:** если .m3d/.cdw не парсятся → принимаем PDF/DXF (OCR + парсинг как у ИИ-Технолога).

### 2.2. 1С Connector

**Назначение:** читает НСИ из 1С:ERP, кеширует, пишет РС.

**Технологии:**
- Python `httpx` или `aiohttp` — async HTTP клиент
- `zeep` или встроенный OData клиент — для OData v3/v4
- SQLite — кеш
- `apscheduler` — для расписания синхронизации

**Интерфейсы:**

```python
# Чтение НСИ
async def get_equipment() -> List[Equipment]
async def get_materials() -> List[Material]
async def get_nomenclature() -> List[Nomenclature]
async def get_departments() -> List[Department]
async def get_rules() -> List[TechRule]
async def get_resource_specifications() -> List[ResourceSpec]

# Запись
async def create_resource_spec(draft: Draft) -> UUID
async def update_resource_spec(rs_id: UUID, changes: Dict) -> None
```

**Кеш SQLite (таблицы):**
```sql
CREATE TABLE nsi_cache (
  entity TEXT,           -- 'equipment', 'material', etc.
  ref_1c TEXT,           -- UUID в 1С
  data JSON,             -- все поля
  hash TEXT,             -- hash для инвалидации
  updated_at TIMESTAMP,
  PRIMARY KEY (entity, ref_1c)
);
```

**Стратегия синхронизации:**
- Pull-based: раз в час (cron)
- Push-based: webhook от 1С (если доступно)
- При старте: full sync, потом инкрементально

**Аутентификация:**
- Basic auth (по умолчанию)
- Token (опционально)
- Windows auth (для АстроЛинукс через LDAP)

### 2.3. LLM-Agent

**Назначение:** генерирует черновик ТК по свойствам детали.

**Технологии:**
- Python `anthropic` SDK
- Redis Queue worker (`rq`)

**Промт:** `bit-technolog-prompt-v0.2.md` (с Few-shot из 4c85941a)

**Входы:**
- Свойства детали (из Watcher)
- Аналоги (из RAG)
- Справочники (из кеша 1С)
- Правила технолога (из кеша 1С)
- Структура предприятия (из кеша 1С)

**Выход:** JSON по 6 вкладкам (summary / route / operations / reasoning / warnings / questions)

**Latency:** ≤ 30 сек (таймаут)

**Кеширование:** если свойства + аналоги совпадают с предыдущим запросом → возврат из кеша.

### 2.4. RAG Index

**Назначение:** поиск аналогов в базе прошлых ТК.

**Технологии:**
- ChromaDB (легковесный векторный store)
- Или `sqlite-vss` (расширение SQLite)
- Embeddings: `voyage-large-2` или `text-embedding-3-small` (OpenAI) или локальная модель

**Что индексируем:**
- Техкарты 4c85941a, 24f5ab23 (из OCR)
- РС из 1С:ERP (синхронизируются)
- Ведомость трудоёмкости 89316e6a

**Поиск:** по обозначению (точное), материалу (точное), габаритам (приблизительное), типу операции (семантическое).

**Match score:** косинусное сходство эмбеддингов, 0-1.

### 2.5. Web UI

**Назначение:** интерфейс технолога.

**Технологии:**
- FastAPI + Jinja2 (серверный рендеринг)
- HTMX (интерактивность без JS-фреймворка)
- Alpine.js (для мелких UI-интеракций)
- PicoCSS или Tailwind (стили, опционально)

**Экраны:** 12 экранов (по `bit-technolog-ux-flow.md`)

### 2.6. PostgreSQL

**Назначение:** наша БД для AI-метаданных, не мастер НСИ.

**Таблицы:**
```sql
CREATE TABLE drafts (
  id UUID PRIMARY KEY,
  detail_ref UUID,                -- ссылка на номенклатуру 1С
  detail_properties JSON,
  llm_output JSON,                -- результат LLM
  status TEXT,                    -- 'new', 'edited', 'approved', 'sent_to_1c'
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  human_edits JSON,               -- лог правок
  rs_id_1c UUID                   -- ID РС в 1С (после записи)
);

CREATE TABLE ai_metadata (
  draft_id UUID REFERENCES drafts(id),
  confidence_overall FLOAT,
  duration_source JSON,           -- {"op_015": "ГОСТ", ...}
  warnings_count INT,
  questions_count INT,
  model_used TEXT,                -- 'claude-sonnet-4-5', etc.
  prompt_tokens INT,
  completion_tokens INT,
  latency_ms INT,
  generated_at TIMESTAMP
);

CREATE TABLE history (
  id UUID PRIMARY KEY,
  draft_id UUID REFERENCES drafts(id),
  user_id UUID,
  action TEXT,                    -- 'created', 'edited', 'approved', 'sent_to_1c', etc.
  changes JSON,
  timestamp TIMESTAMP
);

CREATE TABLE sync_log (
  id UUID PRIMARY KEY,
  entity TEXT,                    -- 'equipment', 'material', etc.
  direction TEXT,                 -- 'in' (from 1C), 'out' (to 1C)
  status TEXT,                    -- 'success', 'error'
  records_count INT,
  duration_ms INT,
  error_message TEXT,
  timestamp TIMESTAMP
);
```

### 2.7. NGINX / Caddy

**Назначение:** reverse proxy, TLS, статика.

**Endpoints:**
- `/` — Web UI
- `/api/*` — REST API для Web UI
- `/health` — health-check
- `/static/*` — статические файлы

---

## 3. API КОНТРАКТЫ (REST для Web UI)

```
GET  /api/details                    # Список деталей (с фильтрами)
GET  /api/details/{id}               # Карточка детали
GET  /api/details/{id}/summary       # Сводка
GET  /api/details/{id}/route         # Маршрут
GET  /api/details/{id}/operations    # Операции
GET  /api/details/{id}/reasoning     # Обоснование
GET  /api/details/{id}/warnings      # Warnings
GET  /api/details/{id}/questions     # Вопросы

POST /api/details/{id}/regenerate    # Перегенерация (с учётом ответов на вопросы)
POST /api/details/{id}/approve       # Утвердить
POST /api/details/{id}/reject        # Отклонить
POST /api/details/{id}/send-to-1c    # Записать РС в 1С
POST /api/details/{id}/refresh-from-kompas  # Обновить из КОМПАС

GET  /api/sync/status                # Статус синхронизации с 1С
POST /api/sync/run                   # Принудительная синхронизация
GET  /api/sync/log                   # Лог обменов

GET  /api/nsi/equipment              # Кешированный справочник оборудования
GET  /api/nsi/materials              # Кешированный справочник материалов
GET  /api/nsi/departments            # Кешированный справочник подразделений
GET  /api/nsi/rules                  # Кешированные правила технолога

GET  /api/health                     # Health-check
```

---

## 4. КОНФИГУРАЦИЯ (config.yaml / .env)

```yaml
# 1C
onec:
  base_url: "http://1c-server/base"
  odata_version: "v4"  # or v3
  auth:
    type: "basic"      # basic | token | windows
    username: "${ONEC_USER}"
    password: "${ONEC_PASSWORD}"
  sync_interval_minutes: 60

# LLM
llm:
  provider: "anthropic"
  model: "claude-sonnet-4-5"
  api_key: "${ANTHROPIC_API_KEY}"
  timeout_seconds: 30
  cache_enabled: true

# Watcher
watcher:
  watch_dirs:
    - "/path/to/konstruktor1"
    - "/path/to/konstruktor2"
  redis_url: "redis://localhost:6379"

# Database
database:
  url: "postgresql://user:pass@localhost:5432/bit_tech"
  pool_size: 10

# App
app:
  base_url: "http://localhost:8080"
  debug: false
  log_level: "INFO"
```

---

## 5. СТРУКТУРА ПРОЕКТА

```
bit-technolog/
├── README.md
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── config.yaml
├── requirements.txt
├── pyproject.toml
│
├── src/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app
│   │   ├── config.py                # Загрузка config + .env
│   │   ├── deps.py                  # Зависимости (DI)
│   │   │
│   │   ├── api/                     # REST API
│   │   │   ├── __init__.py
│   │   │   ├── details.py           # /api/details/*
│   │   │   ├── sync.py              # /api/sync/*
│   │   │   ├── nsi.py               # /api/nsi/*
│   │   │   └── health.py
│   │   │
│   │   ├── web/                     # Web UI (Jinja2 + HTMX)
│   │   │   ├── __init__.py
│   │   │   ├── routes.py
│   │   │   ├── templates/
│   │   │   │   ├── base.html
│   │   │   │   ├── index.html       # Список
│   │   │   │   ├── detail.html      # Карточка
│   │   │   │   ├── sync.html        # Синхронизация
│   │   │   │   └── partials/        # HTMX partials
│   │   │   └── static/
│   │   │       ├── css/
│   │   │       └── js/
│   │   │
│   │   ├── services/                # Бизнес-логика
│   │   │   ├── __init__.py
│   │   │   ├── llm_agent.py         # LLM-агент
│   │   │   ├── rag.py               # RAG поиск
│   │   │   ├── one_c_connector.py   # 1С Connector
│   │   │   ├── kompas_watcher.py    # Watcher КОМПАС
│   │   │   ├── techcard_validator.py
│   │   │   └── sync_scheduler.py    # APScheduler
│   │   │
│   │   ├── models/                  # Pydantic модели
│   │   │   ├── __init__.py
│   │   │   ├── detail.py
│   │   │   ├── techcard.py
│   │   │   ├── equipment.py
│   │   │   ├── material.py
│   │   │   └── one_c.py
│   │   │
│   │   ├── db/                      # БД
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # SQLAlchemy base
│   │   │   ├── session.py           # Async session
│   │   │   └── models.py            # ORM модели
│   │   │
│   │   ├── prompts/                 # Промты
│   │   │   ├── techcard_v0.2.txt
│   │   │   └── few_shots/
│   │   │       └── 4c85941a.json
│   │   │
│   │   └── workers/                 # RQ workers
│   │       ├── __init__.py
│   │       ├── llm_worker.py
│   │       └── sync_worker.py
│   │
├── data/                            # Данные (в gitignore)
│   ├── rag/                         # ChromaDB
│   ├── cache/                       # Кеш НСИ
│   └── uploads/                     # Входящие .m3d/.cdw
│
├── tests/
│   ├── unit/
│   │   ├── test_llm_agent.py
│   │   ├── test_rag.py
│   │   ├── test_one_c_connector.py
│   │   └── test_watcher.py
│   ├── integration/
│   │   ├── test_full_flow.py
│   │   └── test_sync.py
│   └── e2e/
│       └── test_technologist_workflow.py
│
├── scripts/
│   ├── init_db.py
│   ├── seed_rag.py
│   └── seed_test_data.py
│
└── docs/
    ├── api.md
    ├── deployment.md
    └── user_guide.md
```

---

## 6. ТЕХНОЛОГИЧЕСКИЙ СТЕК

| Слой | Технология | Версия | Почему |
|---|---|---|---|
| Runtime | Python | 3.11+ | Стабильность, async |
| Web framework | FastAPI | 0.110+ | Async, авто-документация, типизация |
| ASGI server | Uvicorn | 0.27+ | Стандарт для FastAPI |
| Templates | Jinja2 | 3.1+ | Стандарт |
| Frontend interactivity | HTMX | 1.9+ | Без JS-фреймворка, on-premise friendly |
| Database (наша) | PostgreSQL | 15+ | Надёжность, JSON-поля |
| Async DB | SQLAlchemy 2.0 + asyncpg | — | Async ORM |
| Migration | Alembic | 1.13+ | Стандарт |
| Queue | Redis + RQ | 7+ / 1.16+ | Лёгкий, надёжный |
| Scheduler | APScheduler | 3.10+ | Async-friendly |
| HTTP client | httpx | 0.27+ | Async, HTTP/2 |
| LLM SDK | anthropic | 0.20+ | Claude |
| RAG | ChromaDB | 0.4+ | Лёгкий, embedded |
| Embeddings | text-embedding-3-small (OpenAI) | — | Дёшево, быстро |
| File watcher | watchdog | 4.0+ | Кросс-платформенный |
| КОМПАС-3D parser | pythonnet + КОМПАС API | — | Windows COM |
| Reverse proxy | Caddy | 2.7+ | Авто-TLS, простой конфиг |
| Container | Docker + Docker Compose | 24+ | On-premise |
| OS | Linux (АстроЛинукс) | — | Требование Техинкома |

**НЕ используем:**
- ❌ Supabase (облако)
- ❌ Next.js (overkill)
- ❌ React/Vue (overkill для on-premise)
- ❌ Cloudflare Workers
- ❌ Stripe (не SaaS)
- ❌ Какие-либо облачные зависимости

---

## 7. БЕЗОПАСНОСТЬ

| Требование | Реализация |
|---|---|
| Аутентификация | Basic auth (по умолчанию), опц. интеграция с LDAP/AD |
| Авторизация | RBAC: технолог / начальник / конструктор / админ |
| Шифрование at rest | PostgreSQL: pgcrypto для чувствительных полей |
| Шифрование in transit | TLS через Caddy (самоподписанный для on-premise) |
| Аудит | history table — все действия логируются |
| Секреты | .env файл, не в git; Docker secrets (опц.) |
| Rate limiting | nginx limit_req для /api/* |
| CORS | Только same-origin |

---

## 8. ПРОИЗВОДИТЕЛЬНОСТЬ

| Метрика | Цель |
|---|---|
| Latency LLM-агента | ≤ 30 сек |
| Latency REST API (без LLM) | ≤ 200 мс |
| Latency REST API (с LLM) | ≤ 35 сек |
| Throughput | 100 одновременных технологов |
| Размер PostgreSQL | ≤ 10 ГБ на 1 год (для 1000 ТК) |
| Размер ChromaDB | ≤ 1 ГБ на 1000 ТК |
| Uptime | 99% в рабочее время (без SLA 24/7) |

---

## 9. МОНИТОРИНГ И ЛОГИРОВАНИЕ

**Логи:**
- Structured logging (JSON)
- Уровни: DEBUG, INFO, WARNING, ERROR
- Ротация: раз в сутки, хранить 30 дней

**Метрики:**
- Prometheus endpoint `/metrics` (если будет нужно)
- Или простой health-check `/health`

**Алерты (опц., v0.2):**
- LLM API timeout > 5 раз подряд
- 1С недоступна > 1 час
- PostgreSQL disk full > 90%

---

## 10. CI/CD (опц., v0.2)

**На старте (v0.1):** ручной деплой через `docker-compose up`.

**Потом (v0.2):**
- GitLab CI / GitHub Actions
- Линтеры: ruff, mypy
- Тесты: pytest, coverage
- Auto-build Docker image

---

## 11. ОГРАНИЧЕНИЯ MVP v0.1

- ❌ Нет multi-tenant (одна установка = один клиент)
- ❌ Нет горизонтального масштабирования (один сервер)
- ❌ Нет HA (high availability)
- ❌ Нет бэкапов (за пределами ответственности — задача заказчика)
- ❌ Нет mobile-приложения

---

## 12. СВЯЗАННЫЕ ДОКУМЕНТЫ

- `bit-technolog-context-v6.md` — общий контекст
- `bit-technolog-requirements.md` — функциональные требования
- `bit-technolog-prompt-v0.2.md` — промт
- `bit-technolog-ux-flow.md` — UX-флоу
- `bit-technolog-nsi-architecture.md` — 1С:ERP как мастер НСИ
- `bit-technolog-tech-spec.md` — ТЗ на разработку

---

**Версия:** 1.0 (2026-07-16)
**Готов к ревью Сергеем и старту разработки.**

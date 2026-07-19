# БИТ.Технолог — прототип

**AI-помощник технолога для ООО «ПК Техинком-Центр»** (производство пожарной техники).
Генерирует черновики техкарт по свойствам детали за 30-60 минут вместо 4-8 часов.

> 🎯 **v0.4.9 готов к пилоту на 27 июля 2026.**
> **Текущая версия:** v0.4.9, 219/219 теста passing, развёрнут на Beget VPS.

## Для кого это

| Кто | Что делает с системой | Документация |
|---|---|---|
| **Технолог** (рядовой) | Генерирует проект ТК, правит, отправляет на проверку | `docs/11-tehnolog-guide.md` |
| **Гл. технолог** (Баранов) | Утверждает, записывает в 1С, смотрит метрики | `docs/11-tehnolog-guide.md` + demo `/demo` |
| **Нач. цеха** (Голубев) | Утверждает как начальник, смотрит что в работе | `docs/11-tehnolog-guide.md` + demo `/demo` |
| **Админ Техинкома** (Сергей) | Настраивает LLM/Telegram/SMTP, бэкапы, обновления | `docs/12-admin-guide.md` |
| **Разработчик** (Mavis) | Развивает, фиксит баги, рефакторит | `docs/02-architecture.md` + `MISTAKES.md` + `CHANGELOG.md` |

**Ключевые роли продукта:**
- **On-premise** — данные не покидают завод (ГОЗ, оборонка)
- **1С:ERP ready** — XML/CSV экспорт ресурсных спецификаций
- **Учится на правках** — каждая правка = сигнал для RAG

## Что это

Деталь от конструктора (материал, масса, шасси) → AI генерирует проект ТК:
- Список операций с оборудованием и временем
- Указание источника оценки (ГОСТ / аналог / правило)
- Уверенность по каждой операции (зелёный/жёлтый/красный)
- Замечания с цитатами (что смущает)
- Вопросы к технологу с вариантами
- Обоснование решений (для руководства)
- Ведомость материалов по ГОСТ 3.1105-2011 (Форма 2)
- Экспорт РС в 1С:ERP (XML)
- Уведомления в Telegram

## Быстрый старт (production на Beget)

```
http://217.114.7.5:8081
Логин: user
Пароль: pass
```

После входа:
1. Переключи роль на «🛡 Админ» (header справа)
2. Зайди в **⚙ Настройки** → введи `LLM_API_KEY` (YandexGPT)
3. Зайди в **🛡 Админ** → дашборд, пользователи, лог входов, LLM-вызовы
4. Зайди в **🎯 Demo** — 5-мин сценарий для руководства

## Быстрый старт (локально)

```powershell
# Windows PowerShell
cd C:\Projects\MiniMax\BIT_Tech
.\start.bat
```

Открыть `http://localhost:8080`.

## Тесты

```bash
PILOT_AUTH_DISABLED=true python -m pytest test_app.py -v
```

**Текущий статус:** **173/173 passing** (50+ сценариев).

## Что в коробке (v0.4.3)

| Модуль | Файлы | Что |
|---|---|---|
| **Backend** | `app.py` (4279 строк) | FastAPI + 75+ endpoints |
| **AI** | `prompts.py` (557 строк) | 5 промтов (общий, welding, electrical, hydraulic, paint) |
| **RAG** | `rag.py` (314 строк) | TF-IDF + cosine + hybrid, on-prem |
| **Импорт ТК** | `importers.py` (327 строк) | Excel/PDF/JSON/Word + drawings upload |
| **Pilot отчёт** | `pilot_report.py` (239 строк) | Markdown + 4 matplotlib графика |
| **Seed** | `techinkom_seed.py` (354 строки) | 15 реальных деталей Техинкома |
| **Frontend** | `templates/` | 18 Jinja2 шаблонов |
| **Тесты** | `test_app.py` | 173 pytest теста |

## Возможности (v0.4.3)

### Основной workflow
- **65+ endpoints** — CRUD деталей, генерация, утверждение, экспорт
- **8 вкладок** в карточке детали: Сводка / Маршрут / Операции / Обоснование / Замечания / Вопросы / РС / Связанные / Чертёж
- **Иерархия** деталь→узел→изделие (для АЦ-6,0-40, рам, платформ)
- **3-step generation** (analyze → draft-fast → refine) + RAG top-3
- **Альтернативы** (2-3 варианта маршрута) + 1-click apply similar
- **Batch generate** до 20 деталей за раз
- **Inline edit** операций с whitelist полей
- **Diff view** между версиями проекта ТК
- **Ведомость материалов (МК-М)** в печатной форме по ГОСТ 3.1105-2011
- **Печатная форма A4** с QR-кодом и подписями

### Специализация AI
- 🔥 **Сварка** — Кедр-300, М21, Св-08Г2С, режимы по толщине, ГОСТ 3.1702-79
- ⚡ **Электрика** — СГУ-100, ПВА, WAGO 222, ГОСТ 23594-79
- 💧 **Гидравлика** — ПН-40, рукава РПМ-ВД-50, опрессовка 1.25×Pраб, ГОСТ 12.3.006-75
- 🎨 **Покраска** — ГФ-021, ПФ-115, ГОСТ 25129-82

### 6 ролей + admin
- 👨‍🔧 Технолог
- 👑 Гл. технолог
- 📏 Нормировщик
- 📐 Конструктор
- 🏭 Нач. цеха
- 🔍 ОТК
- 🛡 **Админ** (новое)

### Админка
- 🛡 Дашборд (метрики системы, БД, LLM, RAG)
- 👥 CRUD пользователей (bcrypt + audit_logins)
- 📋 Лог входов (кто, IP, user-agent, успех/ошибка)
- 🤖 Лог LLM-вызовов (фильтры: model, errors_only, days, limit)
- 💾 Запуск backup.sh через UI
- 🔄 RAG rebuild
- 💻 Системные метрики (psutil-like)
- ⚙ **Глобальные настройки** (Fernet encryption) — LLM/Telegram/SMTP/лимиты через UI

### Безопасность
- **HTTP Basic Auth** через `PILOT_USERS` (.env) или БД-pilot_users (bcrypt)
- **CSRF** opt-in через `PILOT_CSRF_ENABLED=true`
- **Fernet (AES-128 + HMAC)** для всех секретов в БД
- **WAL mode** SQLite с busy_timeout
- **Path traversal protection** при загрузке файлов
- **Whitelist** форматов и лимитов размера
- **152-ФЗ** — audit_logins (152 compliance для ПДн)

## Ключевые эндпоинты

**Основные:**
- `GET /` — список деталей с search + pagination + статусами
- `GET /detail/{id}` — карточка детали (8 вкладок)
- `GET /detail/{id}/print` — печатная форма (A4, МК-М, QR, подписи)
- `GET /detail/{id}/diff/{v1}/{v2}` — сравнение версий
- `POST /api/generate` — генерация (op_type: welding/electrical/hydraulic/paint)
- `POST /api/approve` — утверждение (auto-index в RAG)

**AI-помощник (3-step flow):**
- `POST /api/analyze` — 3-5 уточняющих вопросов
- `POST /api/draft-fast` — быстрый draft (3 операции)
- `POST /api/refine` — полный маршрут + RAG top-3
- `POST /api/alternatives` — 2-3 варианта маршрута
- `POST /api/apply-similar` — 1-click применить похожую ТК

**Импорт (4 формата):**
- `POST /api/import/tk` — Excel/PDF/JSON/Word
- `POST /api/import/drawing/{detail_id}` — upload чертежа (50 МБ)
- `GET /api/import/stats`

**Админка:**
- `GET /admin` — дашборд
- `GET /admin/users` — CRUD пользователей
- `GET /admin/login-log` — лог входов
- `GET /admin/llm-calls` — LLM-лог с фильтрами
- `GET /admin/system` — метрики системы
- `GET /admin/settings` — глобальные настройки
- `POST /api/admin/backup` — запуск backup
- `POST /api/admin/rag-rebuild` — переиндексация RAG

**Экспорт:**
- `GET /api/export/excel` / `POST /api/export/pdf` — печатные формы
- `GET /api/export/onec-csv?detail_id=...` — CSV для 1С:ERP
- `GET /api/1c/export/rs/{detail_id}` — XML для 1С:ERP
- `GET /api/audit/export` — audit log в JSON
- `GET /api/export/all` — вся БД в JSON

## Стек

- **Backend:** Python 3.12 / FastAPI / SQLite (WAL mode)
- **Frontend:** Jinja2 + HTMX + vanilla CSS (16px базовый шрифт)
- **AI:** YandexGPT через OpenAI-совместимый SDK
- **RAG:** TF-IDF + cosine + hybrid (scikit-learn, on-prem)
- **Security:** HTTP Basic Auth + CSRF + Fernet (AES-128)
- **Deploy:** systemd + Beget VPS, backup cron 03:00
- **Тесты:** pytest (173 теста)

## Учтено для России

- **YandexGPT** (российский LLM, не западный)
- **ГОСТ 3.1105-2011, 3.1702-79, 23594-79, 12.3.006-75, 25129-82** в промтах
- **ЕТС** коды профессий (19905 Сварщик, 19861 Электромонтажник)
- **Рубли** во всей экономике
- **on-premise архитектура** (можно развернуть у Техинкома)
- **152-ФЗ** — audit_logins
- **Без Cloudflare** (в РФ блокируется)
- **Без западных CDN** — htmx/qrcode локально
- **Beget** (российский хостинг)
- **Открытые либы** (MIT/BSD) — FastAPI, sklearn, openpyxl, pdfplumber

## Структура

```
bit-technolog-prototype/
├── app.py                    # 4279 строк — FastAPI endpoints
├── rag.py                    # 314 строк — RAG-индекс
├── prompts.py                # 557 строк — 5 промтов
├── importers.py              # 327 строк — импорт ТК
├── pilot_report.py           # 239 строк — генератор отчёта
├── techinkom_seed.py         # 354 строки — 15 деталей Техинкома
├── few_shot.py               # 156 строк — примеры для LLM
├── test_app.py               # 173 pytest теста
├── requirements.txt
├── start.bat                 # Запуск (Windows)
├── templates/                # 18 Jinja2 шаблонов
├── static/                   # htmx + qrcode (локально) + style.css
├── docs/                     # 11 файлов документации
└── bit_technolog.db          # SQLite (создаётся автоматически)
```

## Документация

Вся документация в [`docs/`](docs/README.md):
- [01-product-design.md](docs/01-product-design.md) — Osterwalder Canvas + цели
- [02-architecture.md](docs/02-architecture.md) — архитектура
- [03-training-architecture.md](docs/03-training-architecture.md) — RAG + MAG
- [04-pilot-roadmap.md](docs/04-pilot-roadmap.md) — план пилота
- [05-techinkom-context.md](docs/05-techinkom-context.md) — контекст Техинкома
- [06-ux-flow.md](docs/06-ux-flow.md) — UX-сценарии
- [07-audit-log.md](docs/07-audit-log.md) — 9 циклов аудита
- [08-competitors.md](docs/08-competitors.md) — конкуренты
- [09-open-questions.md](docs/09-open-questions.md) — открытые вопросы
- [10-product-fit-and-roadmap.md](docs/10-product-fit-and-roadmap.md) — gap-анализ

## Лицензия

Internal prototype for «Первый БИТ» / «ПК Техинком-Центр».
Не для публичного распространения.

## Контакты

- **Разработка:** Mavis (AI-ассистент)
- **Заказчик:** Сергей Жуков
- **Завод:** ПК «Техинком-Центр» (Москва)

---

*Версия: v0.4.3. Дата: 2026-07-19. Тесты: 173/173. Pilot: 27 июля 2026.*

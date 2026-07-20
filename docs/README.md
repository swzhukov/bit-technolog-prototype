# БИТ.Технолог — Проектная документация

> **AI-помощник технолога для создания техкарт в 1С:ERP**
> Версия: **v0.4.12** · Дата: 2026-07-20 · Статус: пилот 27 июля 2026

---

## Что это такое

БИТ.Технолог — on-premise веб-приложение, которое помогает технологу на заводе создавать
технологические карты (ТК) на детали в 5–10 раз быстрее, чем вручную в Excel/1С.
В основе — AI-генерация маршрута обработки с учётом:

- **RAG** — библиотеки готовых техкарт, типовых операций, ГОСТов
- **Few-shot learning** — 3 эталонных примера (сварка, гидравлика, электрика)
- **Лемматизация синонимов** — «ст3» = «09Г2С», «MIG» = «полуавтомат»
- **Экономика** — расчёт себестоимости по процессам цехов

Первая инсталляция: **ООО «ПК Техинком-Центр»** (Москва, Спортивная) —
производитель пожарных автоцистерн.

---

## Для кого эта документация

| Аудитория | Что читать |
|---|---|
| **Технолог (исполнитель)** | [`11-tehnolog-guide.md`](11-tehnolog-guide.md) + [`14-roles-user-guide.md`](14-roles-user-guide.md) §Технолог |
| **Гл. технолог (утверждающий)** | [`14-roles-user-guide.md`](14-roles-user-guide.md) §Гл. технолог |
| **Нормировщик** | [`14-roles-user-guide.md`](14-roles-user-guide.md) §Нормировщик |
| **ОТК / Контролёр** | [`14-roles-user-guide.md`](14-roles-user-guide.md) §ОТК |
| **Нач. цеха** | [`14-roles-user-guide.md`](14-roles-user-guide.md) §Нач. цеха |
| **Конструктор** | [`14-roles-user-guide.md`](14-roles-user-guide.md) §Конструктор |
| **Админ Техинкома** | [`12-admin-guide.md`](12-admin-guide.md) + [`17-deployment.md`](17-deployment.md) + [`19-security-compliance.md`](19-security-compliance.md) |
| **Разработчик** | [`13-developer-guide.md`](13-developer-guide.md) + [`02-architecture.md`](02-architecture.md) + [`15-api-reference.md`](15-api-reference.md) + [`16-database-schema.md`](16-database-schema.md) |
| **Руководство Техинкома** | [`01-product-design.md`](01-product-design.md) + [`10-product-fit-and-roadmap.md`](10-product-fit-and-roadmap.md) |
| **Безопасник / юрист** | [`19-security-compliance.md`](19-security-compliance.md) + [`09-open-questions.md`](09-open-questions.md) |
| **Все, у кого что-то сломалось** | [`18-troubleshooting.md`](18-troubleshooting.md) + [`20-faq.md`](20-faq.md) |

---

## Содержание

### 📐 Проектирование и продукт

- [`01-product-design.md`](01-product-design.md) — продуктовый дизайн: цели, гипотезы, метрики
- [`02-architecture.md`](02-architecture.md) — техническая архитектура: стек, модули, потоки данных
- [`03-training-architecture.md`](03-training-architecture.md) — как обучать RAG: few-shot, лемматизация, бенчмарки
- [`04-pilot-roadmap.md`](04-pilot-roadmap.md) — roadmap пилота: 4 недели до 27 июля
- [`05-techinkom-context.md`](05-techinkom-context.md) — контекст Техинкома: продукция, процессы, люди
- [`06-ux-flow.md`](06-ux-flow.md) — UX-флоу: 6 ролей, сценарии использования
- [`08-competitors.md`](08-competitors.md) — конкуренты: СПРУТ-ТП,ADEM,TechTrans и др.
- [`09-open-questions.md`](09-open-questions.md) — открытые вопросы (37 пунктов)
- [`10-product-fit-and-roadmap.md`](10-product-fit-and-roadmap.md) — product/market fit и roadmap

### 🛠️ Разработка

- [`13-developer-guide.md`](13-developer-guide.md) — гайд для разработчика: setup, тесты, деплой
- [`15-api-reference.md`](15-api-reference.md) — полный API-справочник (все endpoint'ы)
- [`16-database-schema.md`](16-database-schema.md) — схема БД: таблицы, индексы, миграции

### 👥 Руководства пользователя

- [`11-tehnolog-guide.md`](11-tehnolog-guide.md) — гайд для технолога: как работать в системе
- [`14-roles-user-guide.md`](14-roles-user-guide.md) — **главное руководство по 7 ролям** (что видит каждая)

### 🚀 Эксплуатация

- [`12-admin-guide.md`](12-admin-guide.md) — гайд для админа Техинкома: настройка, мониторинг, бэкапы
- [`17-deployment.md`](17-deployment.md) — полный deployment guide: VPS, systemd, cron, логи
- [`18-troubleshooting.md`](18-troubleshooting.md) — troubleshooting: типичные проблемы и решения
- [`19-security-compliance.md`](19-security-compliance.md) — 152-ФЗ, GDPR, ИБ, шифрование, retention
- [`20-faq.md`](20-faq.md) — часто задаваемые вопросы

### 📊 Аудит

- [`07-audit-log.md`](07-audit-log.md) — журнал аудитов v1–v8 (167 замечаний, 72 закрыто)
- [`AUDIT_v1.md` — `AUDIT_v8.md`](../AUDIT_v8.md) — детальные отчёты по каждому циклу

---

## Краткая сводка (1 страница)

| | |
|---|---|
| **Стек** | FastAPI + Jinja2 + HTMX + SQLite (WAL) |
| **AI** | YandexGPT Lite через OpenAI-совместимый API |
| **RAG** | TF-IDF + cosine + hybrid, своя реализация (без OpenAI embeddings) |
| **Ролей** | 7 (технолог / гл.технолог / нормировщик / конструктор / нач.цеха / ОТК / админ) |
| **Лимит LLM** | 200₽/день, оповещение при 80% |
| **Тестов** | 252/252 passing, ~30 сек прогон |
| **Строк кода** | ~8000 (Python) + ~5000 (HTML/CSS/JS) |
| **Деплой** | Beget VPS, systemd + cron, без Docker |
| **Безопасность** | CSRF, CSP, rate limiting, Fernet, bcrypt+gpg, audit log |
| **Пилот** | 27 июля 2026 (через 7 дней) |
| **Заказчик** | ООО «ПК Техинком-Центр» |
| **Куратор** | Сергей Жуков (Первый БИТ) |

---

## Версионирование

Текущая версия: **v0.4.12**

История:
- v0.4.12 (2026-07-20) — BUG-2026-07-20-02: AI-блок виден для новых деталей
- v0.4.11 (2026-07-20) — BUG-2026-07-20-01: визуальная индикация роли (badge)
- v0.4.10 (2026-07-19) — BUG-2026-07-19-01/02: RBAC + surface None-safe
- v0.4.9 — F15.7: admin.py через APIRouter (admin endpoints вынесены)
- v0.4.8 — v8 аудит: 27 замечаний, +3 закрыто (init_db cleanup, error 500 debugging, логотип)
- v0.4.0–v0.4.7 — основные фичи, 7 циклов аудита

См. полный changelog в [`20-faq.md`](20-faq.md) § История версий.

---

## Лицензия

MIT. Свободное использование, модификация, распространение.
См. [`LICENSE`](../LICENSE) (MIT + 14 зависимостей с лицензиями).

---

## Контакты

- **Куратор проекта (PM):** Сергей Жуков, Первый БИТ
- **Заказчик (пилот):** ООО «ПК Техинком-Центр», Москва
- **Главный контакт у заказчика:** Баранов (гл.технолог), Голубев (директор)
- **Тех. поддержка:** через issue в GitHub или Telegram PM

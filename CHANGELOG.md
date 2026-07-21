# CHANGELOG — БИТ.Технолог

Все значимые изменения в продукте. Формат: [Keep a Changelog](https://keepachangelog.com).

## [v0.4.9] — 2026-07-19 — F15, F16 (audit v1→v3)

### Added (F15)
- **F15.1**: db.py (17KB, 22 функции) — DB layer выделен из app.py
- **F15.2-7**: auth.py, settings.py, notify.py, llm.py, economics.py, learning.py — 6 модулей
- `/pilot/learning` endpoint + template — дашборд тренда acceptance rate
- `/api/pilot/learning` — JSON для графиков

### Added (F16 — 3 цикла аудита)
- **F16.1**: auto-metrics (session_start, time_to_card, acceptance через diff)
- **F16.2**: pymorphy2 лемматизация + 30+ синонимов для RAG
- **F16.3**: 3 few-shot примера (сварка, гидравлика, электрика)
- **F16.4**: CSRF default ON (opt-out через PILOT_CSRF_DISABLED)
- **F16.7**: 4 критичных UX-фикса — toast, кастомный 404, reopen, pre-approve checklist
- **F16.8**: soft-delete для операций + restore
- **F16.9**: keyboard shortcuts, breadcrumbs, print styles, badge в nav
- **V3-2**: CSP middleware (Content-Security-Policy)
- **V3-3**: rate limiting (10/min для LLM, 5/5min для импорта)
- **V3-5**: backup через Python sqlite3 (fallback если нет CLI)
- **V3-12**: alert при 80% дневного лимита LLM

### Changed
- CSRF: opt-in → default ON
- TF-IDF: raw → pymorphy2 + синонимы
- Few-shot: 1 пример → 3 (auto-select по типу детали)
- app.py: 4416 строк (структура с дубликатами) → 4618 (после добавлений)

### Deprecated
- PILOT_CSRF_ENABLED (заменён на PILOT_CSRF_DISABLED)

### Fixed
- F12-CRIT-1: 404 без навигации → кастомный 404.html
- F12-CRIT-2: inline-edit без feedback → тост "Сохранено"
- F12-CRIT-3: нет возврата approved в работу → /api/reopen
- F12-CRIT-4: нет защиты от небрежного утверждения → pre-approve checklist
- F12-CRIT-5: метрики собирались вручную → auto при approve

### Security
- CSRF default ON (вместо opt-in)
- CSP для всех HTML ответов
- Security headers: X-Content-Type-Options, X-Frame-Options, Referrer-Policy
- Rate limiting для LLM и admin endpoints
- .master_key добавлен в .gitignore

### Tests
- 194 → 219 (+25 тестов для F16.1-9 и V3-2/3)

---

## [v0.4.8] — 2026-07-19

### Fixed
- U1-U12: 12 UX-фиксов по аудиту
- M1: role-based action buttons
- M2: бэйджи модели/шасси/уровня/версии КД
- M3: ручное e2e тестирование
- M4: MISTAKES.md в репо (M1-M12)

### Tests: 186/186

---

## [v0.4.7] — 2026-07-19

### Fixed
- M1: role-based action buttons в detail.html
- M2: бэйджи модели/шасси/уровня/версии
- M3: ручное e2e

### Tests: 186/186

---

## [v0.4.6] — 2026-07-19

### Fixed
- @asynccontextmanager lifespan (вместо deprecated @app.on_event)
- get_setting/get_daily_cost устойчивы к свежей БД

### Tests: 180/180

---

## [v0.4.5] — 2026-07-19

### Added
- RAG-метрика на /pilot
- verify_magic_bytes() в importers
- 11-tehnolog-guide.md

### Tests: 180/180

---

## [v0.4.4] — 2026-07-19

### Changed
- Терминология ЕСКД: "черновик"→"проект ТК", "warnings"→"замечания"
- Прогресс-бар при генерации (7 фаз)
- Ведомость материалов МК-М по ГОСТ 3.1105-2011

### Tests: 173/173

---

## [v0.4.3] — 2026-07-19

### Added
- Глобальные настройки через админку (Fernet encryption)
- app_settings table, SETTING_REGISTRY (15 настроек)
- 4 группы: LLM/Telegram/SMTP/Лимиты

### Tests: 167/167

---

## [v0.4.2] — 2026-07-19

### Added
- Admin role + 11 admin endpoints
- pilot_users + audit_logins tables (bcrypt + sha256)
- Role switcher в header (7 ролей)

### Tests: 150/150

---

## [v0.4.1] — 2026-07-19

### Added
- Pilot Report (Markdown + 4 matplotlib charts)
- Role-based UI
- Diff view для версий
- Notifications (email + Telegram dry-run)

### Tests: 130/130

---

## [v0.3.x — v0.4.0] — ранее

- 11 SQLite tables
- CRUD для details, drafts, versions, edits
- RAG (TF-IDF + cosine + hybrid)
- Process-based pricing (economics)
- 4 роли → 6 → 7
- 28 → 35 → 87 → 119 → 130 тестов
- Развёрнут на Beget VPS, production-ready

## M31 (2026-07-21) — v0.6 prototype

**4 спринта за один коммит** (Sprint 0+1+2+3):
- mock_llm.py (11KB) — обёртка для 6 типов задач
- 5 пользователей (tech_pilot, baranov, golubev, vorobyev, itadmin), все с паролем `demo`
- 5 новых таблиц: change_notices, tech_rules, rs_profiles, etalons, pilot_metrics
- 1 извещение (И-2026-014), 4 правила технолога, 3 профиля РС
- 9 экранов: /dashboard, /help, /products, /v6/detail/{id}, /notices, /profiles, /knowledge, /llm-admin
- Дизайн: тёмный header #22303f, красный brand #c8102e, BEM-классы
- Production: 247f469, Basic Auth user:pass
- 290/290 tests passing
